from caisse.domain import receipt


def test_render_receipt_contains_lines_total_and_payments() -> None:
    rendered = receipt.render_receipt(
        order_number="2026-10-05-0001",
        table_label="1",
        counter_number=None,
        items=[
            receipt.ReceiptLine(name="Poisson braisé", quantity=2, line_total_xof=7000),
            receipt.ReceiptLine(
                name="Attiéké", quantity=2, line_total_xof=2000, note="sans piment"
            ),
        ],
        payments=[
            receipt.ReceiptPayment(method="CASH", amount_xof=9000, change_xof=1000),
        ],
        total_ttc_xof=9000,
        header_name="RESTAURANT CHEZ SYLLA PLUS",
        header_address="Yopougon",
        header_phone="0102030405",
        footer="Merci de votre visite",
        width=48,
    )
    assert "2026-10-05-0001" in rendered
    assert "Table 1" in rendered
    assert "Poisson braisé" in rendered
    assert "(sans piment)" in rendered
    assert "9 000 XOF" in rendered
    assert "Espèces" in rendered
    assert "1 000 XOF" in rendered  # rendu monnaie
    assert "Merci de votre visite" in rendered
    assert all(len(line) <= 48 for line in rendered.splitlines())


def test_render_receipt_counter_sale_has_no_table() -> None:
    rendered = receipt.render_receipt(
        order_number="2026-10-05-0002",
        table_label=None,
        counter_number=7,
        items=[receipt.ReceiptLine(name="Jus de bissap", quantity=1, line_total_xof=1000)],
        payments=[receipt.ReceiptPayment(method="CARD", amount_xof=1000)],
        total_ttc_xof=1000,
        header_name="RESTAURANT CHEZ SYLLA PLUS",
        header_address=None,
        header_phone=None,
        footer="",
        width=48,
    )
    assert "Comptoir n° 7" in rendered
    assert "Table" not in rendered


def test_render_z_report_contains_totals_and_variance() -> None:
    rendered = receipt.render_z_report(
        z_number=3,
        business_date="2026-10-05",
        opening_float_xof=20000,
        gross_ttc_xof=50000,
        by_payment_method=[receipt.PaymentMethodAmount(method="CASH", amount_xof=50000)],
        expected_cash_xof=70000,
        counted_cash_xof=69500,
        variance_xof=-500,
        cancelled_orders=1,
        removed_items=2,
        header_name="RESTAURANT CHEZ SYLLA PLUS",
        footer="",
        width=48,
    )
    assert "RAPPORT Z n° 3" in rendered
    assert "50 000 XOF" in rendered
    assert "-500 XOF" in rendered
    assert "1 / 2" in rendered
