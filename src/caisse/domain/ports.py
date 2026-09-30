"""Ports vers l'extérieur (impression, FNE, horloge). Implémentés dans `infrastructure/`,
toujours remplaçables par un mock."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class PrinterStatus:
    agent_online: bool
    printer_online: bool
    paper: str | None
    width: int | None


class Printer(Protocol):
    def status(self) -> PrinterStatus: ...

    def print(
        self, content: str, *, qr: str | None, open_drawer: bool, cut: bool = True
    ) -> None: ...

    def open_drawer(self) -> None: ...


@dataclass(frozen=True, slots=True)
class FneResult:
    external_number: str
    qr_payload: str
    raw: dict[str, Any]


class FneProvider(Protocol):
    def submit(self, payload: dict[str, Any], *, timeout: float) -> FneResult: ...
