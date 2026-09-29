import pytest
from caisse.domain.enums import StockMovementType
from caisse.domain.stock_rules import (
    validate_movement_quantity,
    calculate_quantity_after,
    is_stock_low,
)
from caisse.errors import CaisseException


def test_validate_movement_quantity_valid():
    validate_movement_quantity(10.0, StockMovementType.PURCHASE_IN)
    validate_movement_quantity(1.5, StockMovementType.SALE_OUT)
    validate_movement_quantity(0.0, StockMovementType.INVENTORY_COUNT)


def test_validate_movement_quantity_invalid():
    with pytest.raises(CaisseException) as exc:
        validate_movement_quantity(-5.0, StockMovementType.PURCHASE_IN)
    assert exc.value.code == "INVALID_STOCK_QUANTITY"

    with pytest.raises(CaisseException) as exc:
        validate_movement_quantity(0.0, StockMovementType.SALE_OUT)
    assert exc.value.code == "INVALID_STOCK_QUANTITY"

    with pytest.raises(CaisseException) as exc:
        validate_movement_quantity(0.0, StockMovementType.ADJUSTMENT)
    assert exc.value.code == "ZERO_STOCK_ADJUSTMENT"


def test_calculate_quantity_after():
    assert calculate_quantity_after(20.0, StockMovementType.PURCHASE_IN, 10.0) == 30.0
    assert calculate_quantity_after(30.0, StockMovementType.SALE_OUT, 4.0) == 26.0
    assert calculate_quantity_after(26.0, StockMovementType.LOSS_OUT, 2.0) == 24.0
    assert calculate_quantity_after(24.0, StockMovementType.RETURN_IN, 1.0) == 25.0
    assert calculate_quantity_after(25.0, StockMovementType.ADJUSTMENT, -3.0) == 22.0
    assert calculate_quantity_after(22.0, StockMovementType.INVENTORY_COUNT, 15.0) == 15.0


def test_is_stock_low():
    assert is_stock_low(current_qty := 3.0, alert_threshold := 5.0) is True
    assert is_stock_low(5.0, 5.0) is True
    assert is_stock_low(-1.0, 5.0) is True
    assert is_stock_low(10.0, 5.0) is False
