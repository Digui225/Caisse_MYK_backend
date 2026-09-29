from fastapi import APIRouter, Depends, status
from caisse.schemas.auth import UserResponse
from caisse.schemas.common import PaginatedResponse

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.get("", response_model=PaginatedResponse[UserResponse], summary="Lister les utilisateurs (Admin)")
async def list_users() -> PaginatedResponse[UserResponse]:
    users = [
        UserResponse(id="0192384a-1000-7000-8000-000000000001", full_name="Awa Koné", role="CAISSIER", is_active=True),
        UserResponse(id="0192384a-1000-7000-8000-000000000002", full_name="Kouassi Jean", role="RESPONSABLE", is_active=True),
        UserResponse(id="0192384a-1000-7000-8000-000000000003", full_name="Isaac Admin", role="ADMIN", is_active=True),
    ]
    return PaginatedResponse(items=users, next_cursor=None)
