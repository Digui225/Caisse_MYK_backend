from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, json_schema_extra={"example": "ENTREPRISE IVOIRIENNE SARL"})
    ncc: Optional[str] = Field(None, max_length=50, json_schema_extra={"example": "2104598B"})
    phone: Optional[str] = Field(None, max_length=50, json_schema_extra={"example": "+2250701020304"})
    email: Optional[str] = Field(None, max_length=100, json_schema_extra={"example": "contact@entreprise.ci"})
    address: Optional[str] = Field(None, max_length=255, json_schema_extra={"example": "Abidjan Cocody Deux Plateaux"})


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    ncc: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
