import uuid

from pydantic import ConfigDict, Field, field_validator

from caisse.schemas.common import Schema

# Format observé sur les FNE (9506466A, 1304777N) : 7 chiffres + 1 lettre
NCC_PATTERN = r"^\d{7}[A-Z]$"


class CustomerCreate(Schema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "company_name": "CONFEDERATION GENERALE DES ENTREPRISES DE COTE D'IVOIRE",
                    "ncc": "9506466A",
                    "phone": "0709080765",
                    "email": "contact@cgeci.ci",
                }
            ]
        }
    )

    company_name: str = Field(min_length=1, max_length=160, description="Raison sociale")
    ncc: str | None = Field(
        default=None,
        pattern=NCC_PATTERN,
        description="N° de compte contribuable : 7 chiffres + 1 lettre (espaces et minuscules "
        "acceptés, normalisés)",
        examples=["9506466A"],
    )
    tax_regime: str | None = Field(default=None, max_length=40, description="Régime d'imposition")
    address: str | None = Field(default=None, max_length=255, description="Adresse")
    phone: str | None = Field(default=None, max_length=32, description="Téléphone")
    email: str | None = Field(default=None, max_length=160, description="E-mail")

    @field_validator("ncc", mode="before")
    @classmethod
    def _normalize_ncc(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.replace(" ", "").upper()
            return value or None
        return value

    @field_validator("company_name", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CustomerOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du client")
    company_name: str = Field(description="Raison sociale")
    ncc: str | None = Field(description="N° de compte contribuable")
    tax_regime: str | None = Field(description="Régime d'imposition")
    address: str | None = Field(description="Adresse")
    phone: str | None = Field(description="Téléphone")
    email: str | None = Field(description="E-mail")
