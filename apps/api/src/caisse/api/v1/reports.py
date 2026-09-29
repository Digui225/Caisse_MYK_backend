from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from caisse.database import get_db
from caisse.deps import get_current_user, require_role
from caisse.models.user import User
from caisse.schemas.report import DashboardKpiResponse
from caisse.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["Tableau de Bord & Rapports"])


@router.get("/dashboard", response_model=DashboardKpiResponse)
def get_dashboard_kpis(
    date: Optional[str] = Query(None, description="Date d'exploitation (YYYY-MM-DD), défaut aujourd'hui"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ReportingService(db)
    return service.get_dashboard_kpis(business_date_str=date)
