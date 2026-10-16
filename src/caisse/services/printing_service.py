"""File d'impression (ticket, tiroir) : mirror du schéma FNE (`services/fne_service.py`) —
créer la ligne, committer, tenter l'appel externe, figer le statut final, committer.

`create_and_print` ne lève jamais : une vente ou une clôture ne doit jamais échouer pour une
raison d'impression (l'imprimante est informative, cf. `ENDPOINTS-TESTABLES.md` §1). Seules les
actions directes (`manual_open_drawer`, `test_print`) propagent une erreur HTTP, puisqu'elles
sont demandées explicitement par un responsable/admin qui doit en connaître le résultat.
"""

import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy.orm import Session

from caisse.domain.enums import PrintJobStatus, PrintJobType
from caisse.domain.ports import Printer, PrintResult
from caisse.errors import (
    NotFoundError,
    PrintAgentUnavailableError,
    PrinterUnavailableError,
    PrintJobNotRetryableError,
)
from caisse.models.print_job import PrintJob
from caisse.repositories import print_jobs as print_jobs_repo
from caisse.schemas.printing import PrintingStatusOut
from caisse.services import audit_service
from caisse.services.audit_service import RequestContext

log = structlog.get_logger()

RETRYABLE_STATUSES = (PrintJobStatus.QUEUED, PrintJobStatus.FAILED)


def _raise_for_direct_error(exc: httpx.HTTPError) -> None:
    """Distingue agent injoignable (connexion/délai) de panne de l'imprimante elle-même
    (l'agent répond, mais en erreur)."""
    if isinstance(exc, httpx.HTTPStatusError):
        raise PrinterUnavailableError() from exc
    raise PrintAgentUnavailableError() from exc


def _attempt(
    db: Session, job: PrintJob, agent: Printer, *, user_id: uuid.UUID, ctx: RequestContext
) -> PrintResult | None:
    # commité PRINTING avant l'appel : si le processus meurt pendant l'appel, le job reste
    # visible dans cet état plutôt que QUEUED, sans être renvoyé à l'aveugle par un worker futur
    job.status = PrintJobStatus.PRINTING
    job.attempts += 1
    db.commit()

    result: PrintResult | None = None
    try:
        result = agent.print(job.rendered or "", qr=None, open_drawer=job.open_drawer)
    except httpx.HTTPError as exc:
        job.status = PrintJobStatus.FAILED
        job.last_error = str(exc)[:500]
    else:
        job.status = PrintJobStatus.DONE if result.printed else PrintJobStatus.FAILED
        if not result.printed:
            job.last_error = "L'agent a répondu printed=false"

    audit_service.log(
        db,
        "print_job.print",
        ctx=ctx,
        user_id=user_id,
        entity="print_job",
        entity_id=job.id,
        after={"status": job.status, "type": job.type, "attempts": job.attempts},
    )
    db.commit()
    return result


def create_and_print(
    db: Session,
    *,
    job_type: PrintJobType,
    agent: Printer,
    rendered: str,
    open_drawer: bool,
    order_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    is_reprint: bool = False,
    user_id: uuid.UUID,
    ctx: RequestContext,
) -> tuple[PrintJob, bool]:
    """Renvoie (job, drawer_opened). Ne lève jamais : voir docstring du module."""
    job = PrintJob(
        type=job_type,
        order_id=order_id,
        session_id=session_id,
        payload=payload or {},
        rendered=rendered,
        open_drawer=open_drawer,
        status=PrintJobStatus.QUEUED,
        is_reprint=is_reprint,
        requested_by=user_id,
    )
    db.add(job)
    db.commit()
    result = _attempt(db, job, agent, user_id=user_id, ctx=ctx)
    return job, bool(result and result.drawer_opened)


def retry(
    db: Session, job_id: uuid.UUID, *, agent: Printer, user_id: uuid.UUID, ctx: RequestContext
) -> PrintJob:
    job = print_jobs_repo.get_for_update(db, job_id)
    if job is None:
        raise NotFoundError(meta={"job_id": str(job_id)})
    if job.status not in RETRYABLE_STATUSES:
        raise PrintJobNotRetryableError(meta={"job_id": str(job_id), "status": job.status})
    _attempt(db, job, agent, user_id=user_id, ctx=ctx)
    return job


def list_jobs(db: Session, *, status: PrintJobStatus | None) -> list[PrintJob]:
    return print_jobs_repo.list_jobs(db, status=status)


def status(db: Session, agent: Printer) -> PrintingStatusOut:
    printer_status = agent.status()
    return PrintingStatusOut(
        agent_online=printer_status.agent_online,
        printer_online=printer_status.printer_online,
        paper=printer_status.paper,
        width=printer_status.width,
        queued_jobs=print_jobs_repo.queued_count(db),
        failed_jobs=print_jobs_repo.failed_count(db),
        last_success_at=print_jobs_repo.last_success_at(db),
    )


def manual_open_drawer(
    agent: Printer, *, user_id: uuid.UUID, ctx: RequestContext, db: Session
) -> bool:
    try:
        agent.open_drawer()
    except httpx.HTTPError as exc:
        audit_service.log(
            db,
            "printing.open_drawer_manual",
            ctx=ctx,
            user_id=user_id,
            entity="printer",
            entity_id=None,
            after={"drawer_opened": False, "error": str(exc)[:500]},
        )
        db.commit()
        _raise_for_direct_error(exc)
    audit_service.log(
        db,
        "printing.open_drawer_manual",
        ctx=ctx,
        user_id=user_id,
        entity="printer",
        entity_id=None,
        after={"drawer_opened": True},
    )
    db.commit()
    return True


def test_print(agent: Printer, *, user_id: uuid.UUID, ctx: RequestContext, db: Session) -> bool:
    try:
        agent.test_print()
    except httpx.HTTPError as exc:
        audit_service.log(
            db,
            "printing.test",
            ctx=ctx,
            user_id=user_id,
            entity="printer",
            entity_id=None,
            after={"printed": False, "error": str(exc)[:500]},
        )
        db.commit()
        _raise_for_direct_error(exc)
    audit_service.log(
        db,
        "printing.test",
        ctx=ctx,
        user_id=user_id,
        entity="printer",
        entity_id=None,
        after={"printed": True},
    )
    db.commit()
    return True
