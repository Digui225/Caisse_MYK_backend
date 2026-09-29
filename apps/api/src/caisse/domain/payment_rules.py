from datetime import datetime
from fastapi import status
from caisse.domain.enums import PaymentMethod
from caisse.errors import CaisseException

# Commandes standard ESC/POS
ESC_INIT = b"\x1b\x40"
ESC_DRAWER_KICK = b"\x1b\x70\x00\x19\xfa"  # Envoi impulsion tiroir DK port RJ11
ESC_CUT_PAPER = b"\x1d\x56\x42\x00"      # Coupe papier avec avance


def validate_payment_amount(amount_xof: int, due_xof: int) -> None:
    """Vérifie que le montant à encaisser est valide vis-à-vis du reste dû."""
    if amount_xof <= 0:
        raise CaisseException(
            code="INVALID_PAYMENT_AMOUNT",
            title="Montant de paiement invalide",
            detail="Le montant du paiement doit être strictement supérieur à 0 XOF.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if amount_xof > due_xof:
        raise CaisseException(
            code="OVERPAYMENT_NOT_ALLOWED",
            title="Montant supérieur au reste dû",
            detail=f"Le montant ({amount_xof} XOF) ne peut pas excéder le reste dû ({due_xof} XOF).",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            meta={"amount_xof": amount_xof, "due_xof": due_xof},
        )


def calculate_change(tendered_xof: int | None, amount_xof: int, method: str) -> int:
    """Calcule le rendu de monnaie en espèces."""
    if method == PaymentMethod.CASH:
        if tendered_xof is not None:
            if tendered_xof < amount_xof:
                raise CaisseException(
                    code="INSUFFICIENT_TENDERED_AMOUNT",
                    title="Montant remis insuffisant",
                    detail=f"Le montant remis ({tendered_xof} XOF) est inférieur au montant à payer ({amount_xof} XOF).",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    meta={"tendered_xof": tendered_xof, "amount_xof": amount_xof},
                )
            return tendered_xof - amount_xof
        return 0
    return 0


def should_open_drawer(method: str, is_reprint: bool = False, is_manual_override: bool = False) -> bool:
    """Règle stricte d'ouverture tiroir : jamais sur ré-impression, oui sur espèces ou action manuelle responsable."""
    if is_reprint:
        return False
    if is_manual_override:
        return True
    return method == PaymentMethod.CASH


def build_esc_pos_bytes(content: str, open_drawer: bool = False, cut: bool = True) -> bytes:
    """Construit la séquence d'octets ESC/POS complète avec tiroir et coupe papier."""
    raw = bytearray(ESC_INIT)
    if open_drawer:
        raw.extend(ESC_DRAWER_KICK)

    # Encodage du texte (remplacement des caractères non supportés)
    raw.extend(content.encode("cp850", errors="replace"))
    raw.extend(b"\n\n\n")

    if cut:
        raw.extend(ESC_CUT_PAPER)

    return bytes(raw)


def format_receipt_text(
    restaurant_info: dict,
    order_info: dict,
    items: list[dict],
    payments: list[dict],
    totals: dict,
    fne_info: dict | None = None,
    is_duplicate: bool = False,
    width: int = 42,
) -> str:
    """Génère le texte structuré et aligné pour le ticket de caisse 42 colonnes."""
    sep_line = "-" * width
    lines = []

    def center(txt: str) -> str:
        return txt.strip().center(width)

    def row(left: str, right: str) -> str:
        left_len = len(left)
        right_len = len(right)
        spaces = width - left_len - right_len
        if spaces < 1:
            return f"{left[: width - right_len - 1]} {right}"
        return f"{left}{' ' * spaces}{right}"

    # 1. En-tête restaurant
    lines.append(center(restaurant_info.get("name", "RESTAURANT MYK")))
    lines.append(center(restaurant_info.get("address", "Abidjan, Côte d'Ivoire")))
    lines.append(center(f"Tél: {restaurant_info.get('phone', '+225 07 00 00 00')}"))
    if restaurant_info.get("ncc") or restaurant_info.get("rccm"):
        lines.append(center(f"NCC: {restaurant_info.get('ncc', '-')} · RCCM: {restaurant_info.get('rccm', '-')}"))

    if is_duplicate:
        lines.append(sep_line)
        lines.append(center("*** DUPLICATA ***"))

    lines.append(sep_line)

    # 2. Informations commande
    lines.append(row("Ticket", order_info.get("order_number", "-")))
    table_label = order_info.get("table_label") or "Comptoir"
    guests = order_info.get("guests_count", 1)
    lines.append(row(f"Table : {table_label}", f"Couverts : {guests}"))
    lines.append(row(f"Caissier : {order_info.get('cashier_name', 'Caisse')}", order_info.get("date_str", "")))
    lines.append(sep_line)

    # 3. Lignes de commande
    for item in items:
        qty = item.get("quantity", 1)
        name = item.get("name", "Article")
        total_price = f"{item.get('line_total_xof', 0):,} F".replace(",", " ")
        lines.append(row(f"{qty} x {name}", total_price))

    lines.append(sep_line)

    # 4. Totaux
    lines.append(row("TOTAL TTC", f"{totals.get('total_ttc_xof', 0):,} F".replace(",", " ")))
    lines.append(row(f"  dont TVA {totals.get('vat_rate', 18)}%", f"{totals.get('total_vat_xof', 0):,} F".replace(",", " ")))
    lines.append(sep_line)

    # 5. Règlements
    for p in payments:
        method_label = p.get("method", "PAIEMENT")
        provider = f" ({p.get('provider')})" if p.get("provider") else ""
        amount_str = f"{p.get('amount_xof', 0):,} F".replace(",", " ")
        lines.append(row(f"{method_label}{provider}", amount_str))

    change = totals.get("change_xof", 0)
    if change > 0:
        lines.append(row("Rendu", f"{change:,} F".replace(",", " ")))

    lines.append(sep_line)

    # 6. Bloc fiscal FNE
    if fne_info and fne_info.get("fne_number"):
        lines.append(center(f"FNE n° {fne_info.get('fne_number')}"))
        if fne_info.get("qr_url"):
            lines.append(center("[ QR Code FNE DGI ]"))
    else:
        lines.append(center("Facture normalisée en cours de transmission"))
        lines.append(center(f"Réf: {order_info.get('order_number', '-')}"))

    lines.append(sep_line)
    lines.append(center(restaurant_info.get("footer", "Merci de votre visite et à bientôt !")))

    return "\n".join(lines)
