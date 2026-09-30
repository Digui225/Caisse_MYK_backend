from fastapi import APIRouter

from caisse.api.v1 import auth, catalog, tables, users

api_router = APIRouter(prefix="/api/v1")
for module in (auth, users, catalog, tables):
    api_router.include_router(module.router)
