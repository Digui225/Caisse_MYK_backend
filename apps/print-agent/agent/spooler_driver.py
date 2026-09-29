import logging
import sys
from typing import Any

logger = logging.getLogger("print-agent.spooler")

# ESC/POS commands
ESC_INIT = b"\x1b\x40"
ESC_DRAWER_KICK = b"\x1b\x70\x00\x19\xfa"
ESC_CUT_PAPER = b"\x1d\x56\x42\x00"

try:
    import win32print  # type: ignore
    HAS_WIN32PRINT = True
except ImportError:
    HAS_WIN32PRINT = False


def print_job_raw(printer_name: str, raw_data: bytes, doc_name: str = "Ticket Caisse") -> bool:
    """Envoie des octets bruts (RAW ESC/POS) directement au Spooler Windows."""
    if not HAS_WIN32PRINT:
        logger.warning(
            "Plateforme non-Windows ou module win32print indisponible. "
            "Simulation de l'impression (RAW bytes: %d octets).",
            len(raw_data),
        )
        return True

    try:
        h_printer = win32print.OpenPrinter(printer_name)
        try:
            h_job = win32print.StartDocPrinter(h_printer, 1, (doc_name, None, "RAW"))
            win32print.StartPagePrinter(h_printer)
            win32print.WritePrinter(h_printer, raw_data)
            win32print.EndPagePrinter(h_printer)
            win32print.EndDocPrinter(h_printer)
            return True
        finally:
            win32print.ClosePrinter(h_printer)
    except Exception as exc:
        logger.error("Erreur d'impression Spooler Windows sur '%s': %s", printer_name, exc)
        raise exc


def open_drawer_only(printer_name: str) -> bool:
    """Envoie une impulsion électrique sur le port DK/RJ11 de l'imprimante pour ouvrir le tiroir."""
    raw_pulse = ESC_INIT + ESC_DRAWER_KICK
    return print_job_raw(printer_name, raw_pulse, doc_name="Ouverture Tiroir")


def get_spooler_status(printer_name: str) -> dict[str, Any]:
    """Interroge l'état de l'imprimante dans le Spooler Windows."""
    if not HAS_WIN32PRINT:
        return {
            "online": True,
            "paper": "ok",
            "model": f"{printer_name} (Mode simulation / Dev)",
            "width": 42,
            "os": sys.platform,
        }

    try:
        h_printer = win32print.OpenPrinter(printer_name)
        try:
            info = win32print.GetPrinter(h_printer, 2)
            status_code = info.get("Status", 0)
            is_offline = bool(status_code & 0x00000080)  # PRINTER_STATUS_OFFLINE
            is_out_of_paper = bool(status_code & 0x00000010)  # PRINTER_STATUS_OUT_OF_PAPER
            is_error = bool(status_code & 0x00000002)  # PRINTER_STATUS_ERROR

            return {
                "online": not (is_offline or is_error),
                "paper": "empty" if is_out_of_paper else "ok",
                "model": printer_name,
                "width": 42,
                "status_code": status_code,
            }
        finally:
            win32print.ClosePrinter(h_printer)
    except Exception as exc:
        logger.warning("Impossible d'obtenir le statut de l'imprimante '%s': %s", printer_name, exc)
        return {
            "online": False,
            "paper": "unknown",
            "model": printer_name,
            "width": 42,
            "error": str(exc),
        }
