"""Pilote ESC/POS. Aucune règle métier : reçoit un texte déjà mis en forme par l'API.

Le périphérique est ouvert puis fermé à chaque job : un débranchement/rebranchement de
l'imprimante ne demande donc pas de redémarrer l'agent.
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from escpos.escpos import Escpos
from escpos.printer import Dummy, Usb

from agent.config import AgentSettings

log = logging.getLogger("print-agent")


class PrinterUnavailable(Exception):
    pass


@dataclass
class Status:
    online: bool
    paper: str  # ok | near_end | empty | unknown
    model: str
    width: int


class EscposDriver:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self._lock = threading.Lock()  # un seul job à la fois sur le port USB

    @contextmanager
    def _printer(self) -> Iterator[Escpos]:
        s = self.settings
        if s.printer_backend == "dummy":
            dummy = Dummy()
            yield dummy
            log.info("[dummy] %d octets envoyés :\n%s", len(dummy.output),
                     dummy.output.decode("cp858", errors="replace"))
            return
        try:
            printer = Usb(s.printer_vendor_id, s.printer_product_id, in_ep=s.printer_in_ep,
                          out_ep=s.printer_out_ep)
            printer.open()
        except Exception as exc:  # usb.core.USBError, DeviceNotFoundError…
            raise PrinterUnavailable(str(exc)) from exc
        try:
            yield printer
        finally:
            printer.close()

    def _setup(self, printer: Escpos) -> None:
        try:
            printer.charcode(self.settings.printer_codepage)
        except Exception:
            log.warning("page de code %s non prise en charge", self.settings.printer_codepage)

    def status(self) -> Status:
        s = self.settings
        model = "dummy" if s.printer_backend == "dummy" else (
            f"usb:{s.printer_vendor_id:04x}:{s.printer_product_id:04x}")
        with self._lock:
            try:
                with self._printer() as printer:
                    paper = "ok" if s.printer_backend == "dummy" else _paper(printer)
                return Status(online=True, paper=paper, model=model, width=s.printer_width)
            except PrinterUnavailable:
                return Status(online=False, paper="unknown", model=model, width=s.printer_width)

    def print(self, content: str, *, qr: str | None, open_drawer: bool, cut: bool) -> None:
        with self._lock, self._printer() as printer:
            # le tiroir s'ouvre dans le même job que le ticket (exigence client)
            if open_drawer:
                printer._raw(self.settings.drawer_pulse_bytes)
            self._setup(printer)
            printer.text(content if content.endswith("\n") else content + "\n")
            if qr:
                printer.qr(qr, size=6, center=True)
            if cut:
                printer.cut()

    def open_drawer(self) -> None:
        with self._lock, self._printer() as printer:
            printer._raw(self.settings.drawer_pulse_bytes)


def _paper(printer: Escpos) -> str:
    """Beaucoup d'imprimantes d'entrée de gamme ne répondent pas : on renvoie `unknown`."""
    try:
        return {2: "ok", 1: "near_end", 0: "empty"}.get(printer.paper_status(), "unknown")
    except Exception:
        return "unknown"
