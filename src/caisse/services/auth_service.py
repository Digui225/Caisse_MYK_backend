import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from caisse.config import get_settings
from caisse.domain.enums import CashSessionStatus, UserRole, role_at_least
from caisse.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    OverrideRequiredError,
    TokenExpiredError,
)
from caisse.models.cash_session import CashSession
from caisse.models.user import DeviceLoginThrottle, OverrideGrant, RefreshToken, User
from caisse.repositories import users as users_repo
from caisse.security import decode_token, encode_token, hash_pin, pin_needs_rehash, utcnow
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext

MAX_LOCK_SECONDS = 15 * 60


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


@dataclass(frozen=True, slots=True)
class OverrideToken:
    token: str
    expires_in: int
    granted_by: User


# --- Temporisation par poste -------------------------------------------------------------


def _throttle_for_update(db: Session, device_id: str) -> DeviceLoginThrottle:
    throttle = db.scalar(
        select(DeviceLoginThrottle)
        .where(DeviceLoginThrottle.device_id == device_id)
        .with_for_update()
    )
    if throttle is None:
        throttle = DeviceLoginThrottle(device_id=device_id, failed_attempts=0, updated_at=utcnow())
        db.add(throttle)
        db.flush()
    return throttle


def _assert_not_locked(throttle: DeviceLoginThrottle, now: datetime) -> None:
    if throttle.locked_until and throttle.locked_until > now:
        raise AccountLockedError(meta={"locked_until": throttle.locked_until.isoformat()})


def _register_failure(
    db: Session, throttle: DeviceLoginThrottle, ctx: RequestContext, now: datetime
) -> None:
    """Blocage progressif : au-delà de PIN_MAX_ATTEMPTS, chaque échec double la durée."""
    settings = get_settings()
    throttle.failed_attempts += 1
    throttle.updated_at = now
    over = throttle.failed_attempts - settings.pin_max_attempts
    locked = over >= 0
    if locked:
        seconds = min(settings.pin_lock_seconds * 2**over, MAX_LOCK_SECONDS)
        throttle.locked_until = now + timedelta(seconds=seconds)
    audit_service.log(
        db, "auth.login_failed", ctx=ctx, after={"failed_attempts": throttle.failed_attempts}
    )
    db.commit()
    if locked:
        raise AccountLockedError(
            meta={
                "locked_until": throttle.locked_until.isoformat() if throttle.locked_until else None
            }
        )
    raise InvalidCredentialsError(
        meta={"remaining_attempts": settings.pin_max_attempts - throttle.failed_attempts}
    )


def _match_pin(db: Session, pin: str, ctx: RequestContext) -> User:
    device_id = ctx.device_id or "unknown"
    now = utcnow()
    throttle = _throttle_for_update(db, device_id)
    _assert_not_locked(throttle, now)
    user = users_repo.find_by_pin(db, pin)
    if user is None:
        _register_failure(db, throttle, ctx, now)
    assert user is not None
    throttle.failed_attempts = 0
    throttle.locked_until = None
    throttle.updated_at = now
    if pin_needs_rehash(user.pin_hash):
        user.pin_hash = hash_pin(pin)
    return user


# --- Jetons ------------------------------------------------------------------------------


def _issue_tokens(db: Session, user: User, device_id: str | None) -> TokenPair:
    settings = get_settings()
    access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    access, _ = encode_token("access", user.id, access_ttl, role=user.role.value)
    jti = uuid.uuid4()
    refresh, refresh_exp = encode_token(
        "refresh", user.id, timedelta(hours=settings.refresh_token_ttl_hours), jti=jti
    )
    db.add(RefreshToken(jti=jti, user_id=user.id, device_id=device_id, expires_at=refresh_exp))
    return TokenPair(access, refresh, int(access_ttl.total_seconds()), user)


def login(db: Session, pin: str, ctx: RequestContext) -> TokenPair:
    user = _match_pin(db, pin, ctx)
    user.last_login_at = utcnow()
    pair = _issue_tokens(db, user, ctx.device_id)
    audit_service.log(db, "auth.login", ctx=ctx, user_id=user.id, entity="user", entity_id=user.id)
    db.commit()
    return pair


def refresh(db: Session, refresh_token: str, ctx: RequestContext) -> TokenPair:
    """Rotation : l'ancien refresh est révoqué, un nouveau est émis."""
    claims = decode_token(refresh_token, "refresh")
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.jti == uuid.UUID(claims["jti"])).with_for_update()
    )
    if stored is None or stored.revoked_at is not None or stored.expires_at <= utcnow():
        raise TokenExpiredError()
    user = users_repo.get(db, stored.user_id)
    if user is None or not user.is_active:
        raise TokenExpiredError()
    pair = _issue_tokens(db, user, ctx.device_id or stored.device_id)
    stored.revoked_at = utcnow()
    stored.replaced_by = uuid.UUID(decode_token(pair.refresh_token, "refresh")["jti"])
    db.commit()
    return pair


def logout(db: Session, refresh_token: str, user: User, ctx: RequestContext) -> None:
    try:
        claims = decode_token(refresh_token, "refresh")
    except TokenExpiredError:
        return  # déjà inutilisable : rien à révoquer
    stored = db.get(RefreshToken, uuid.UUID(claims["jti"]))
    if stored is not None and stored.user_id == user.id and stored.revoked_at is None:
        stored.revoked_at = utcnow()
    audit_service.log(db, "auth.logout", ctx=ctx, user_id=user.id)
    db.commit()


def authenticate_access(db: Session, token: str) -> User:
    claims = decode_token(token, "access")
    user = users_repo.get(db, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise TokenExpiredError()
    return user


# --- Élévation ponctuelle ----------------------------------------------------------------


def authorize_override(
    db: Session,
    pin: str,
    *,
    requested_by: User,
    action: str,
    required_role: UserRole,
    ctx: RequestContext,
) -> OverrideToken:
    """Un responsable saisit son PIN sur le poste du caissier → jeton 60 s, usage unique."""
    granter = _match_pin(db, pin, ctx)
    if not role_at_least(granter.role, required_role):
        db.rollback()
        raise OverrideRequiredError(meta={"required_role": required_role})
    ttl = timedelta(seconds=get_settings().override_token_ttl_seconds)
    jti = uuid.uuid4()
    token, expires_at = encode_token(
        "override", granter.id, ttl, jti=jti, action=action, requested_by=str(requested_by.id)
    )
    db.add(
        OverrideGrant(
            jti=jti,
            granted_by_user_id=granter.id,
            requested_by_user_id=requested_by.id,
            action=action,
            expires_at=expires_at,
        )
    )
    audit_service.log(
        db,
        "auth.override_granted",
        ctx=ctx,
        user_id=requested_by.id,
        acting_as_user_id=granter.id,
        after={"action": action},
    )
    db.commit()
    return OverrideToken(token, int(ttl.total_seconds()), granter)


def consume_override(
    db: Session, token: str | None, *, requested_by: User, action: str, required_role: UserRole
) -> User:
    """À appeler dans la transaction de l'opération protégée. Retourne le responsable."""
    if not token:
        raise OverrideRequiredError(meta={"action": action, "required_role": required_role})
    try:
        claims = decode_token(token, "override")
    except TokenExpiredError as exc:
        raise OverrideRequiredError(meta={"action": action, "reason": "expired"}) from exc
    grant = db.scalar(
        select(OverrideGrant).where(OverrideGrant.jti == uuid.UUID(claims["jti"])).with_for_update()
    )
    granter = users_repo.get(db, grant.granted_by_user_id) if grant else None
    if (
        grant is None
        or granter is None
        or grant.consumed_at is not None
        or grant.action != action
        or grant.requested_by_user_id != requested_by.id
        or grant.expires_at <= utcnow()
        or not role_at_least(granter.role, required_role)
    ):
        raise OverrideRequiredError(meta={"action": action, "reason": "invalid"})
    grant.consumed_at = utcnow()
    return granter


# --- Session courante --------------------------------------------------------------------


def current_open_session(db: Session) -> CashSession | None:
    """MVP mono-caisse : la session non clôturée de la caisse. Le rattachement poste → caisse
    viendra avec le multi-postes."""
    return db.scalar(
        select(CashSession)
        .where(CashSession.status != CashSessionStatus.CLOSED)
        .order_by(CashSession.opened_at.desc())
        .limit(1)
    )
