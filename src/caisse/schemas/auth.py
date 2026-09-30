from pydantic import ConfigDict, Field

from caisse.domain.enums import UserRole
from caisse.schemas.common import OpenSessionOut, Schema, UserOut

Pin = Field(pattern=r"^\d{4,8}$", description="Code PIN (chiffres uniquement)", examples=["482913"])


class LoginRequest(Schema):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"pin": "482913", "device_id": "poste-1"}]}
    )

    pin: str = Pin
    device_id: str = Field(
        min_length=1,
        max_length=64,
        description="Identifiant du poste ; les PIN faux sont comptés par poste",
        examples=["poste-1"],
    )


class TokenResponse(Schema):
    access_token: str = Field(description="Jeton d'accès, à envoyer dans `Authorization: Bearer`")
    refresh_token: str = Field(
        description="Jeton de renouvellement (usage unique : révoqué à chaque /auth/refresh)"
    )
    token_type: str = Field(default="bearer", description="Toujours « bearer »")
    expires_in: int = Field(description="Durée de validité du jeton d'accès, en secondes")
    user: UserOut = Field(description="Utilisateur connecté")
    open_session: OpenSessionOut | None = Field(
        description="Session de caisse ouverte, null si aucune"
    )


class RefreshRequest(Schema):
    refresh_token: str = Field(description="Jeton de renouvellement reçu à la connexion")


class MeResponse(Schema):
    user: UserOut = Field(description="Utilisateur connecté")
    open_session: OpenSessionOut | None = Field(
        description="Session de caisse ouverte, null si aucune"
    )


class OverrideRequest(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"pin": "654321", "action": "order.remove_item", "required_role": "RESPONSABLE"}
            ]
        }
    )

    pin: str = Field(
        pattern=r"^\d{4,8}$",
        description="PIN du responsable qui autorise (saisi sur le poste du demandeur)",
        examples=["654321"],
    )
    action: str = Field(
        min_length=1,
        max_length=64,
        description="Opération autorisée ; le jeton ne vaut que pour elle",
        examples=["order.remove_item"],
    )
    required_role: UserRole = Field(
        default=UserRole.RESPONSABLE, description="Rôle minimal exigé de celui qui autorise"
    )


class OverrideResponse(Schema):
    override_token: str = Field(
        description="Jeton à envoyer dans `X-Override-Token` (usage unique, lié à l'action "
        "et au demandeur)"
    )
    expires_in: int = Field(description="Durée de validité, en secondes")
    granted_by: UserOut = Field(description="Responsable qui a autorisé")
