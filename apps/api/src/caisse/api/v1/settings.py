from typing import Any
from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["Paramètres Système"])


@router.get("", summary="Consulter les paramètres système")
async def get_settings() -> dict[str, Any]:
    return {
        "restaurant_name": "Restaurant MYK",
        "ncc": "1234567A",
        "rccm": "CI-ABJ-2026-B-0000",
        "address": "Abidjan, Côte d'Ivoire",
        "phone": "+225 0102030405",
        "default_vat_rate": 18.0,
        "print_width": 48,
        "screen_lock_timeout_seconds": 120,
    }
