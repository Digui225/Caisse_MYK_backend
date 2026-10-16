import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from caisse.deps import Admin, Ctx, CurrentUser, DbSession, PrintAgentDep, Responsable
from caisse.domain.enums import PrintJobStatus
from caisse.schemas.common import Page
from caisse.schemas.printing import OpenDrawerOut, PrintingStatusOut, PrintJobOut, TestPrintOut
from caisse.services import printing_service

router = APIRouter(prefix="/printing", tags=["Impression"])

JobId = Annotated[uuid.UUID, Path(description="Identifiant du travail d'impression")]


@router.get("/status", response_model=PrintingStatusOut, summary="État de l'impression")
def status_(_: CurrentUser, db: DbSession, agent: PrintAgentDep) -> PrintingStatusOut:
    """Agent, imprimante et file. N'échoue jamais : `agent_online: false` si l'agent
    ne répond pas, c'est informatif (`/health/ready` expose le même état)."""
    return printing_service.status(db, agent)


@router.post(
    "/open-drawer",
    response_model=OpenDrawerOut,
    status_code=status.HTTP_200_OK,
    summary="Ouverture manuelle du tiroir",
)
def open_drawer(user: Responsable, db: DbSession, ctx: Ctx, agent: PrintAgentDep) -> OpenDrawerOut:
    """Action tracée, hors vente (ex. correction de caisse). Erreurs : `503 PRINTER_UNAVAILABLE`,
    `503 PRINT_AGENT_UNAVAILABLE`."""
    opened = printing_service.manual_open_drawer(agent, user_id=user.id, ctx=ctx, db=db)
    return OpenDrawerOut(drawer_opened=opened)


@router.get("/jobs", response_model=Page[PrintJobOut], summary="File d'impression")
def jobs(
    _: CurrentUser,
    db: DbSession,
    status_filter: Annotated[PrintJobStatus | None, Query(alias="status")] = None,
) -> Page[PrintJobOut]:
    items = printing_service.list_jobs(db, status=status_filter)
    return Page(items=[PrintJobOut.model_validate(job) for job in items])


@router.post(
    "/jobs/{job_id}/retry",
    response_model=PrintJobOut,
    summary="Rejeu d'un travail d'impression",
)
def retry(
    job_id: JobId, user: CurrentUser, db: DbSession, ctx: Ctx, agent: PrintAgentDep
) -> PrintJobOut:
    """Erreurs : `404 NOT_FOUND`, `409 PRINT_JOB_NOT_RETRYABLE` (déjà `DONE` ou en cours)."""
    job = printing_service.retry(db, job_id, agent=agent, user_id=user.id, ctx=ctx)
    return PrintJobOut.model_validate(job)


@router.post("/test", response_model=TestPrintOut, summary="Ticket de test")
def test_print(user: Admin, db: DbSession, ctx: Ctx, agent: PrintAgentDep) -> TestPrintOut:
    """Erreurs : `503 PRINTER_UNAVAILABLE`, `503 PRINT_AGENT_UNAVAILABLE`."""
    printed = printing_service.test_print(agent, user_id=user.id, ctx=ctx, db=db)
    return TestPrintOut(printed=printed)
