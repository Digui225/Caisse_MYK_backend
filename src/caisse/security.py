"""Hachage des PIN (Argon2) et jetons JWT (accès, refresh, override)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from caisse.config import get_settings
from caisse.errors import TokenExpiredError

TokenType = Literal["access", "refresh", "override"]

_hasher = PasswordHasher()


def hash_pin(pin: str) -> str:
    return _hasher.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        return _hasher.verify(pin_hash, pin)
    except (VerificationError, InvalidHashError):
        return False


def pin_needs_rehash(pin_hash: str) -> bool:
    return _hasher.check_needs_rehash(pin_hash)


def utcnow() -> datetime:
    return datetime.now(UTC)


def encode_token(
    token_type: TokenType,
    subject: uuid.UUID,
    ttl: timedelta,
    jti: uuid.UUID | None = None,
    **claims: Any,
) -> tuple[str, datetime]:
    settings = get_settings()
    now = utcnow()
    expires_at = now + ttl
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(jti or uuid.uuid4()),
        **claims,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise TokenExpiredError() from exc
    if payload.get("type") != expected_type:
        raise TokenExpiredError("Type de jeton inattendu")
    return payload
