from enum import StrEnum


class UserRole(StrEnum):
    CAISSIER = "CAISSIER"
    RESPONSABLE = "RESPONSABLE"
    ADMIN = "ADMIN"


class SessionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class CashMovementType(StrEnum):
    IN = "IN"
    OUT = "OUT"


class OrderStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    MOBILE_MONEY = "MOBILE_MONEY"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CREDIT = "CREDIT"
    OTHER = "OTHER"


class StockMovementType(StrEnum):
    PURCHASE_IN = "PURCHASE_IN"
    SALE_OUT = "SALE_OUT"
    RETURN_IN = "RETURN_IN"
    LOSS_OUT = "LOSS_OUT"
    ADJUSTMENT = "ADJUSTMENT"
    INVENTORY_COUNT = "INVENTORY_COUNT"


class FneDocumentType(StrEnum):
    FNE = "FNE"
    REFUND = "REFUND"
    RNE = "RNE"
    DAILY_SUMMARY = "DAILY_SUMMARY"


class FneStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SUBMITTING = "SUBMITTING"
    CERTIFIED = "CERTIFIED"
    FAILED = "FAILED"
    MANUAL = "MANUAL"



class PrintJobType(StrEnum):
    RECEIPT = "RECEIPT"
    X_REPORT = "X_REPORT"
    Z_REPORT = "Z_REPORT"
    FNE = "FNE"
    ORDER_TICKET = "ORDER_TICKET"


class PrintJobStatus(StrEnum):
    QUEUED = "QUEUED"
    PRINTING = "PRINTING"
    DONE = "DONE"
    FAILED = "FAILED"
