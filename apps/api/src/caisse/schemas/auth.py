from typing import Literal
from pydantic import BaseModel, Field
from caisse.schemas.common import BaseSchema


class LoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6, description="Code PIN numérique (6 chiffres)")
    device_id: str = Field(..., description="Identifiant unique du poste caisse")


class UserResponse(BaseSchema):
    id: str
    full_name: str
    role: Literal["CAISSIER", "RESPONSABLE", "ADMIN"]
    is_active: bool = True


class OpenSessionInfo(BaseSchema):
    id: str
    business_date: str
    cash_register_id: str


class LoginResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    user: UserResponse
    open_session: OpenSessionInfo | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class OverrideRequest(BaseModel):
    manager_pin: str = Field(..., min_length=4, max_length=6)
    reason: str = Field(..., min_length=3)
    target_action: str


class OverrideResponse(BaseSchema):
    override_token: str
    expires_in: int = 60
    authorized_by: str
