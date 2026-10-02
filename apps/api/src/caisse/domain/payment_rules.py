import unicodedata
from datetime import datetime
from fastapi import status
from caisse.domain.enums import PaymentMethod
from caisse.errors import CaisseException

# Commandes standard ESC/POS pour imprimantes thermiques (XP-58IIH / POS-58 / 80mm)
ESC_INIT = b"\x1b\x40"
FS_CANCEL_CHINESE = b"\x1c\x2e"          # Annulation stricte du mode caractères chinois (Xprinter / POS-58)
ESC_SELECT_CP437 = b"\x1b\x74\x00"       # Sélection table de caractères standard PC437
ESC_SELECT_CP1252 = b"\x1b\x74\x10"      # Sélection table Windows-1252
ESC_DRAWER_KICK = b"\x1b\x70\x00\x19\xfa"  # Envoi impulsion tiroir DK port RJ11
ESC_CUT_PAPER = b"\x1d\x56\x42\x00"        # Coupe papier avec avance massicot


def sanitize_french_text(text: str) -> str:
    """Remplace les accents et caractères typographiques par leurs équivalents ASCII 7 bits
    pour éviter tout décodage fantôme en idéogrammes chinois (GBK/GB2312) sur imprimantes thermiques."""
    replacements = {
        "·": ".",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        "–": "-",
        "—": "-",
        "°": "o",
        "€": "EUR",
        "œ": "oe",
        "Œ": "OE",
        "æ": "ae",
        "Æ": "AE",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    nfd = unicodedata.normalize("NFD", text)
    ascii_text = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return ascii_text.encode("ascii", errors="replace").decode("ascii")


def build_esc_pos_qr(data: str, size: int = 4) -> bytes:
    """Génère la séquence ESC/POS native GS ( k pour imprimer un QR Code 2D (Modèle 2)."""
    data_bytes = data.encode("ascii", errors="replace")
    data_len = len(data_bytes) + 3
    pL = data_len & 0xFF
    pH = (data_len >> 8) & 0xFF

    res = bytearray()
    res.extend(b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00")          # 1. Modèle 2
    res.extend(b"\x1d\x28\x6b\x03\x00\x31\x43" + bytes([size]))  # 2. Taille module (dots)
    res.extend(b"\x1d\x28\x6b\x03\x00\x31\x45\x31")              # 3. Correction d'erreur Niveau M
    res.extend(b"\x1d\x28\x6b" + bytes([pL, pH]) + b"\x31\x50\x30" + data_bytes)  # 4. Données
    res.extend(b"\x1d\x28\x6b\x03\x00\x31\x51\x30")              # 5. Impression
    return bytes(res)


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


from pathlib import Path

_CACHED_LOGO_BYTES: bytes | None = None


def get_esc_pos_logo_bytes() -> bytes | None:
    """Charge la séquence raster ESC/POS monochrome du logo Sylla Plus."""
    global _CACHED_LOGO_BYTES
    if _CACHED_LOGO_BYTES is not None:
        return _CACHED_LOGO_BYTES

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    bin_file = assets_dir / "sylla_logo_escpos.bin"
    if bin_file.exists():
        try:
            _CACHED_LOGO_BYTES = bin_file.read_bytes()
            return _CACHED_LOGO_BYTES
        except Exception:
            pass
    return None


def build_esc_pos_bytes(
    content: str,
    open_drawer: bool = False,
    cut: bool = True,
    qr_data: str | None = None,
    include_logo: bool = True,
) -> bytes:
    """Construit la séquence d'octets ESC/POS complète avec :
    - Réinitialisation et annulation forcée du mode chinois
    - Marge d'amorce haute (évite de rogner l'en-tête)
    - Déclenchement RJ11 tiroir-caisse si demandé
    - Traduction ASCII 7-bit de l'intégralité du texte
    - Rendu du logo graphique monochrome thermique
    - Rendu natif des QR codes 2D
    - Marge basse d'éjection (4 sauts de ligne)
    - Coupe papier si supporté
    """
    raw = bytearray()

    # 1. Reset initialisation
    raw.extend(ESC_INIT)

    # 2. Désactivation du mode idéogrammes chinois
    raw.extend(FS_CANCEL_CHINESE)

    # 3. Sélection code page PC437
    raw.extend(ESC_SELECT_CP437)

    # 4. Marge supérieure pour dégager le massicot / barre dentelée
    raw.extend(b"\n")

    # 5. Tiroir RJ11
    if open_drawer:
        raw.extend(ESC_DRAWER_KICK)

    # 6. Traitement des lignes de texte et détection de balises [LOGO] et [QR_CODE: ...]
    logo_already_printed = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped == "[LOGO]":
            if not logo_already_printed and include_logo:
                logo_bytes = get_esc_pos_logo_bytes()
                if logo_bytes:
                    raw.extend(logo_bytes)
                    raw.extend(b"\n")
                    logo_already_printed = True
        elif stripped == "[NO_LOGO]":
            pass
        elif stripped.startswith("[QR_CODE:") and stripped.endswith("]"):
            qr_content = stripped[len("[QR_CODE:"): -1].strip()
            if qr_content:
                raw.extend(b"\n\x1b\x61\x01")  # Centrage
                raw.extend(build_esc_pos_qr(qr_content, size=4))
                raw.extend(b"\x1b\x61\x00\n")  # Retour alignement gauche
        elif stripped == "[QR_CODE]":
            pass
        else:
            clean_line = sanitize_french_text(line)
            raw.extend(clean_line.encode("ascii", errors="replace"))
            raw.extend(b"\n")

    # Si aucun tag [LOGO] explicite n'était dans le texte mais que logo demandé
    if include_logo and not logo_already_printed and "[NO_LOGO]" not in content:
        # Inséré au début juste après marge
        pass

    # 7. QR Code additionnel explicite
    if qr_data:
        raw.extend(b"\n\x1b\x61\x01")
        raw.extend(build_esc_pos_qr(qr_data, size=4))
        raw.extend(b"\x1b\x61\x00\n")

    # 8. Marge basse complète pour que tout le contenu sorte au-delà de la lame
    raw.extend(b"\n\n\n\n")

    # 9. Coupe papier
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
    width: int = 32,
    welcome_message: str | None = None,
) -> str:
    """Génère le texte structuré et aligné pour le ticket de caisse thermique 32 colonnes (58mm)."""
    sep_line = "-" * width
    lines = []

    def center(txt: str) -> str:
        txt = txt.strip()
        if len(txt) > width:
            return txt[:width]
        return txt.center(width)

    def row(left: str, right: str) -> str:
        left_str = str(left)
        right_str = str(right)
        spaces = width - len(left_str) - len(right_str)
        if spaces < 1:
            max_left = width - len(right_str) - 1
            if max_left > 0:
                return f"{left_str[:max_left]} {right_str}"
            return f"{left_str} {right_str}"
        return f"{left_str}{' ' * spaces}{right_str}"

    # 1. En-tête officiel restaurant avec logo
    lines.append("[LOGO]")

    name = restaurant_info.get("name", "SYLLA PLUS").upper()
    if name != "SYLLA PLUS":
        lines.append(center(name))

    addr = restaurant_info.get("address", "Cocody Riviera Palmeraie · Abidjan")
    if addr:
        if len(addr) > width and ("·" in addr or "." in addr or "," in addr):
            clean_addr = addr.replace("·", ",").replace(".", ",")
            for part in clean_addr.split(","):
                p = part.strip()
                if p:
                    lines.append(center(p))
        else:
            lines.append(center(addr))

    phone = restaurant_info.get("phone", "+225 07 58 00 00 00")
    if phone:
        lines.append(center(f"Tel : {phone}"))

    ncc = restaurant_info.get("ncc", "2104598B")
    if ncc:
        lines.append(center(f"NCC : {ncc}"))

    if is_duplicate:
        lines.append(sep_line)
        lines.append(center("*** DUPLICATA ***"))

    lines.append(sep_line)

    # 2. Informations commande
    order_num = str(order_info.get("order_number", "-"))
    table_label = str(order_info.get("table_label") or "Comptoir")
    table_str = table_label if table_label.upper().startswith("TABLE") else f"TABLE {table_label}"
    cmd_label = f"COMMANDE #{order_num}" if not order_num.startswith("#") else f"COMMANDE {order_num}"

    if len(cmd_label) + len(table_str) + 1 <= width:
        lines.append(row(cmd_label, table_str))
    else:
        lines.append(row("Ticket", order_num))
        lines.append(row(table_str, f"Couverts : {order_info.get('guests_count', 1)}"))

    date_str = order_info.get("date_str", "")
    cashier = order_info.get("cashier_name", "Marc")
    if date_str:
        if len(f"Date : {date_str}") + len(f"Caissier : {cashier}") + 1 <= width:
            lines.append(row(f"Date : {date_str}", f"Caissier : {cashier}"))
        else:
            lines.append(row("Date", date_str))
            lines.append(row("Caissier", cashier))
    else:
        lines.append(row("Caissier", cashier))

    # Message d'accueil secondaire
    welcome = welcome_message or restaurant_info.get("welcome_message")
    if welcome:
        lines.append(sep_line)
        lines.append(center(welcome))

    lines.append(sep_line)

    # 3. Détail des articles
    lines.append(row("ARTICLES", "PRIX"))
    lines.append(sep_line)

    for item in items:
        qty = item.get("quantity", 1)
        item_name = item.get("name", "Article")
        total_price = f"{item.get('line_total_xof', 0):,} F".replace(",", " ")
        lines.append(row(f"{qty}x {item_name}", total_price))

    lines.append(sep_line)

    # 4. Totaux & Taxes
    if "subtotal_ht_xof" in totals:
        lines.append(row("Sous-total HT", f"{totals['subtotal_ht_xof']:,} F".replace(",", " ")))
    elif "total_vat_xof" in totals and "total_ttc_xof" in totals:
        subtotal_ht = totals["total_ttc_xof"] - totals["total_vat_xof"]
        lines.append(row("Sous-total HT", f"{subtotal_ht:,} F".replace(",", " ")))

    vat_rate = totals.get("vat_rate", 18)
    vat_amt = totals.get("total_vat_xof", 0)
    lines.append(row(f"TVA ({vat_rate}%)", f"{vat_amt:,} F".replace(",", " ")))
    lines.append(row("TOTAL TTC", f"{totals.get('total_ttc_xof', 0):,} F CFA".replace(",", " ")))

    lines.append(sep_line)

    # 5. Règlements & Rendu
    for p in payments:
        method = p.get("method", "PAIEMENT")
        if method == "CASH" or "ESPECE" in str(method).upper():
            method_label = "Reglement Especes :"
        else:
            method_label = f"Paiement {method} :"
        amount_str = f"{p.get('amount_xof', 0):,} F".replace(",", " ")
        lines.append(row(method_label, amount_str))

    tendered = totals.get("tendered_xof")
    if tendered:
        lines.append(row("Recu caissier :", f"{tendered:,} F".replace(",", " ")))

    change = totals.get("change_xof", 0)
    if change > 0 or tendered:
        lines.append(row("Monnaie rendue :", f"{change:,} F".replace(",", " ")))

    lines.append(sep_line)

    # 6. Bloc fiscal DGI / FNE (uniquement si facture normalisée demandée ou présente)
    fne_number = (fne_info or {}).get("fne_number") or order_info.get("fne_number")
    fne_qr_url = (fne_info or {}).get("qr_url") or order_info.get("fne_qr_url")
    if fne_number or fne_qr_url:
        lines.append(center("FACTURE NORMALISEE DGI"))
        if fne_number:
            lines.append(center(str(fne_number)))
        if fne_qr_url:
            lines.append(f"[QR_CODE: {fne_qr_url}]")
        lines.append(sep_line)

    # 7. Pied de ticket
    footer = restaurant_info.get("footer", "Merci de votre visite · A tres bientot !")
    if footer:
        if len(footer) > width and ("·" in footer or "." in footer or "!" in footer):
            clean_footer = footer.replace("·", ".").replace("!", "!.")
            for part in clean_footer.split("."):
                p = part.strip()
                if p:
                    lines.append(center(p))
        else:
            lines.append(center(footer))

    return "\n".join(lines)
