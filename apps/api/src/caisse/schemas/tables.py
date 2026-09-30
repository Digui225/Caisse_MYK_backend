from pydantic import BaseModel, Field
from caisse.schemas.common import BaseSchema


class TableResponse(BaseSchema):
    id: str
    label: str
    zone: str = "Salle"
    seats: int = 4
    sort_order: int = 0
    is_active: bool = True


class CreateTableRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=50, description="Nom ou numéro de la table")
    zone: str = Field("Salle", min_length=1, max_length=50, description="Zone du restaurant (ex: Salle, Terrasse)")
    seats: int = Field(4, ge=1, le=50, description="Nombre de places assises / capacité en personnes")
    sort_order: int = Field(0, description="Ordre d'affichage")


class UpdateTableRequest(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=50, description="Nom ou numéro mis à jour")
    zone: str | None = Field(None, min_length=1, max_length=50, description="Zone mise à jour")
    seats: int | None = Field(None, ge=1, le=50, description="Nombre de places mis à jour")
    sort_order: int | None = Field(None, description="Ordre d'affichage")
    is_active: bool | None = Field(None, description="Statut actif / archivé")


class TableBoardItem(BaseSchema):
    id: str
    label: str
    zone: str
    seats: int
    is_occupied: bool
    current_order_id: str | None = None
    current_order_number: str | None = None
    current_total_ttc_xof: int = 0
    guests_count: int | None = None
    opened_at: str | None = None
    server_name: str | None = None
    items_count: int | None = None
    service_step: str | None = None


class TableBoardResponse(BaseSchema):
    tables: list[TableBoardItem]
    open_orders_count: int
    total_in_progress_xof: int
