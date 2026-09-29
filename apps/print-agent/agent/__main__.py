import os
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from agent.spooler_driver import (
    print_job_raw,
    open_drawer_only,
    get_spooler_status,
    ESC_INIT,
    ESC_DRAWER_KICK,
    ESC_CUT_PAPER,
)

PRINTER_NAME = os.getenv("PRINTER_NAME", "POS-80")
PORT = int(os.getenv("PORT", "8090"))
HOST = os.getenv("HOST", "127.0.0.1")

app = FastAPI(title="Caisse MYK - Print Agent (Windows Spooler)", version="1.0.0")


class PrintPayload(BaseModel):
    content: str
    qr: str | None = None
    open_drawer: bool = False
    cut: bool = True


@app.get("/status", summary="État de l'imprimante dans le Spooler Windows")
def get_status():
    return get_spooler_status(PRINTER_NAME)


@app.post("/print", status_code=status.HTTP_200_OK, summary="Imprimer un ticket")
def print_receipt(payload: PrintPayload):
    raw = bytearray(ESC_INIT)

    # 1. Impulsion tiroir si demandée
    if payload.open_drawer:
        raw.extend(ESC_DRAWER_KICK)

    # 2. Contenu texte
    raw.extend(payload.content.encode("cp850", errors="replace"))
    raw.extend(b"\n\n\n")

    # 3. Coupe papier
    if payload.cut:
        raw.extend(ESC_CUT_PAPER)

    try:
        print_job_raw(PRINTER_NAME, bytes(raw), doc_name="Ticket de Caisse")
        return {"status": "PRINTED", "open_drawer": payload.open_drawer}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'impression : {str(exc)}",
        )


@app.post("/open-drawer", status_code=status.HTTP_200_OK, summary="Ouvrir le tiroir manuellement")
def open_drawer():
    try:
        open_drawer_only(PRINTER_NAME)
        return {"status": "DRAWER_OPENED"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur impulsion tiroir : {str(exc)}",
        )


@app.post("/test-print", status_code=status.HTTP_200_OK, summary="Ticket de test")
def test_print():
    test_content = (
        "==========================================\n"
        "           TEST IMPRIMANTE MYK            \n"
        "        Agent Spooler Windows OK          \n"
        "==========================================\n"
        "Modèle : " + PRINTER_NAME + "\n"
        "Encodage : CP850 / ESC-POS\n"
        "==========================================\n"
    )
    raw = bytearray(ESC_INIT)
    raw.extend(test_content.encode("cp850", errors="replace"))
    raw.extend(b"\n\n\n")
    raw.extend(ESC_CUT_PAPER)

    try:
        print_job_raw(PRINTER_NAME, bytes(raw), doc_name="Test Impression")
        return {"status": "TEST_PRINT_SENT"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur test d'impression : {str(exc)}",
        )


def start():
    uvicorn.run("agent.__main__:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    start()
