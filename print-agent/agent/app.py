import hmac
import logging
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from agent.config import get_settings
from agent.escpos_driver import EscposDriver, PrinterUnavailable

log = logging.getLogger("print-agent")
settings = get_settings()
driver = EscposDriver(settings)


def check_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if not settings.agent_token:
        return
    expected = f"Bearer {settings.agent_token}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Jeton invalide")


app = FastAPI(title="Agent d'impression Caisse", dependencies=[Depends(check_token)])


class PrintRequest(BaseModel):
    content: str
    qr: str | None = None
    open_drawer: bool = False
    cut: bool = True


def _unavailable(exc: PrinterUnavailable) -> HTTPException:
    log.error("imprimante indisponible : %s", exc)
    return HTTPException(status_code=503, detail={"code": "PRINTER_UNAVAILABLE",
                                                  "detail": str(exc)})


@app.get("/status")
def status() -> dict[str, object]:
    s = driver.status()
    return {"online": s.online, "paper": s.paper, "model": s.model, "width": s.width}


@app.post("/print")
def print_job(job: PrintRequest) -> dict[str, object]:
    try:
        driver.print(job.content, qr=job.qr, open_drawer=job.open_drawer, cut=job.cut)
    except PrinterUnavailable as exc:
        raise _unavailable(exc) from exc
    return {"printed": True, "drawer_opened": job.open_drawer}


@app.post("/open-drawer")
def open_drawer() -> dict[str, bool]:
    try:
        driver.open_drawer()
    except PrinterUnavailable as exc:
        raise _unavailable(exc) from exc
    return {"drawer_opened": True}


@app.post("/test-print")
def test_print() -> dict[str, bool]:
    width = settings.printer_width
    lines = [
        "TICKET DE TEST".center(width),
        "-" * width,
        f"Largeur    : {width} caractères",
        f"Page code  : {settings.printer_codepage}",
        f"Date       : {datetime.now():%d/%m/%Y %H:%M:%S}",
        "Accents    : é è à ç ô û — 9 500 F",
        "-" * width,
        "Si ce ticket est lisible, l'agent fonctionne.".center(width),
    ]
    try:
        driver.print("\n".join(lines), qr="https://caisse.local/test", open_drawer=False,
                     cut=True)
    except PrinterUnavailable as exc:
        raise _unavailable(exc) from exc
    return {"printed": True}
