from fastapi import APIRouter

from caisse.api.v1 import auth, catalog, customers, fne, orders, sessions, tables, users

api_router = APIRouter(prefix="/api/v1")
for module in (auth, users, catalog, tables, sessions, orders, customers, fne):
    api_router.include_router(module.router)
