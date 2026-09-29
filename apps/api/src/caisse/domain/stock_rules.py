from fastapi import status
from caisse.domain.enums import StockMovementType
from caisse.errors import CaisseException


def validate_movement_quantity(quantity: float, movement_type: str) -> None:
    """Valide la cohérence de la quantité selon le type de mouvement."""
    if movement_type == StockMovementType.INVENTORY_COUNT:
        if quantity < 0:
            raise CaisseException(
                code="INVALID_STOCK_QUANTITY",
                title="Quantité d'inventaire négative",
                detail="La quantité constatée lors d'un inventaire ne peut pas être négative.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    elif movement_type == StockMovementType.ADJUSTMENT:
        if quantity == 0:
            raise CaisseException(
                code="ZERO_STOCK_ADJUSTMENT",
                title="Ajustement nul",
                detail="La quantité d'ajustement ne peut pas être égale à zéro.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    else:
        if quantity <= 0:
            raise CaisseException(
                code="INVALID_STOCK_QUANTITY",
                title="Quantité de stock invalide",
                detail="La quantité du mouvement doit être strictement supérieure à 0.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


def calculate_quantity_after(current_quantity: float, movement_type: str, quantity: float) -> float:
    """Calcule le nouveau niveau de stock après application du mouvement."""
    if movement_type in [StockMovementType.PURCHASE_IN, StockMovementType.RETURN_IN]:
        return round(current_quantity + quantity, 3)
    elif movement_type in [StockMovementType.SALE_OUT, StockMovementType.LOSS_OUT]:
        return round(current_quantity - quantity, 3)
    elif movement_type == StockMovementType.ADJUSTMENT:
        return round(current_quantity + quantity, 3)
    elif movement_type == StockMovementType.INVENTORY_COUNT:
        return round(quantity, 3)
    else:
        raise CaisseException(
            code="UNKNOWN_MOVEMENT_TYPE",
            title="Type de mouvement inconnu",
            detail=f"Le type de mouvement '{movement_type}' n'est pas reconnu.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def is_stock_low(quantity: float, alert_threshold: float) -> bool:
    """Détermine si le stock est en alerte (seuil bas ou négatif)."""
    return quantity <= alert_threshold
