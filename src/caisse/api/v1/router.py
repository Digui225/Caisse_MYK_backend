from fastapi import APIRouter

from caisse.api.v1 import (
    auth,
    catalog,
    customers,
    fne,
    orders,
    payments,
    printing,
    sessions,
    tables,
    users,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    auth,
    users,
    catalog,
    tables,
    sessions,
    orders,
    payments,
    customers,
    fne,
    printing,
):
    api_router.include_router(module.router)
