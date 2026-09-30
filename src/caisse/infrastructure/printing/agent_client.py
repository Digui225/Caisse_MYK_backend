"""Client HTTP de l'agent d'impression (service systemd hors Docker, ADR-13)."""

import time
from typing import Any

import httpx

from caisse.config import get_settings
from caisse.domain.ports import PrinterStatus

_STATUS_CACHE_SECONDS = 5.0


class PrintAgentClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 3.0) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        self._cached: tuple[float, PrinterStatus] | None = None

    def status(self) -> PrinterStatus:
        now = time.monotonic()
        if self._cached and now - self._cached[0] < _STATUS_CACHE_SECONDS:
            return self._cached[1]
        try:
            data: dict[str, Any] = (
                self._client.get("/status", timeout=1.5).raise_for_status().json()
            )
            status = PrinterStatus(
                agent_online=True,
                printer_online=bool(data.get("online")),
                paper=data.get("paper"),
                width=data.get("width"),
            )
        except httpx.HTTPError:
            status = PrinterStatus(agent_online=False, printer_online=False, paper=None, width=None)
        self._cached = (now, status)
        return status

    def print(self, content: str, *, qr: str | None, open_drawer: bool, cut: bool = True) -> None:
        self._client.post(
            "/print", json={"content": content, "qr": qr, "open_drawer": open_drawer, "cut": cut}
        ).raise_for_status()

    def open_drawer(self) -> None:
        self._client.post("/open-drawer").raise_for_status()


_client: PrintAgentClient | None = None


def get_print_agent() -> PrintAgentClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = PrintAgentClient(settings.print_agent_url, settings.print_agent_token)
    return _client
