from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class FneDocumentResponse(BaseModel):
    id: str
    order_id: str
    customer_id: Optional[str] = None
    document_type: str
    status: str
    invoice_number: Optional[str] = None
    qr_url: Optional[str] = None
    fne_token: Optional[str] = None
    payload: dict[str, Any]
    response_payload: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int
    submitted_at: Optional[datetime] = None
    certified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FneGenerateRequest(BaseModel):
    order_id: str
    customer_id: Optional[str] = None


class FneRetryRequest(BaseModel):
    pass


class FneExportFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
