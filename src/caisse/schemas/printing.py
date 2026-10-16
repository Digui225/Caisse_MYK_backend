import uuid
from datetime import datetime

from pydantic import Field

from caisse.domain.enums import PrintJobStatus, PrintJobType
from caisse.schemas.common import Schema


class PrintingStatusOut(Schema):
    agent_online: bool = Field(description="L'agent d'impression répond")
    printer_online: bool = Field(description="L'imprimante répond à l'agent")
    paper: str | None = Field(description="État du papier (`ok`, `low`…), selon l'agent")
    width: int | None = Field(description="Largeur en caractères rapportée par l'agent")
    queued_jobs: int = Field(description="Travaux en file (`QUEUED`)")
    failed_jobs: int = Field(description="Travaux en échec (`FAILED`)")
    last_success_at: datetime | None = Field(description="Dernière impression réussie")


class PrintJobOut(Schema):
    id: uuid.UUID = Field(description="Identifiant du travail d'impression")
    type: PrintJobType = Field(description="RECEIPT, X_REPORT, Z_REPORT, FNE ou ORDER_TICKET")
    order_id: uuid.UUID | None = Field(description="Commande concernée, s'il y en a une")
    session_id: uuid.UUID | None = Field(description="Session de caisse concernée, s'il y en a une")
    status: PrintJobStatus = Field(description="QUEUED, PRINTING, DONE ou FAILED")
    attempts: int = Field(description="Nombre de tentatives")
    last_error: str | None = Field(description="Dernière erreur, le cas échéant")
    is_reprint: bool = Field(description="Ré-impression d'un ticket déjà imprimé")
    created_at: datetime = Field(description="Date de création du travail")


class OpenDrawerOut(Schema):
    drawer_opened: bool = Field(description="Le tiroir s'est bien ouvert")


class TestPrintOut(Schema):
    printed: bool = Field(description="Le ticket de test a été imprimé")
