from pydantic import BaseModel, Field
from caisse.schemas.common import BaseSchema


class CustomerResponse(BaseSchema):
    id: str
    company_name: str
    ncc: str
    tax_regime: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    created_at: str


class CustomerCreateRequest(BaseModel):
    company_name: str
    ncc: str = Field(..., min_length=5, description="Numéro de Compte Contribuable")
    tax_regime: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
