# bot/validators.py
"""
Input validation for CLI arguments passed to the trading bot.
All validators raise ValueError with a human-readable message on failure.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional

# Supported order types as an ordered tuple (used for help text ordering)
# STOP = Binance Futures stop-limit (requires both stopPrice and price)
VALID_ORDER_TYPES = ("MARKET", "LIMIT", "STOP_MARKET", "STOP")
VALID_SIDES = ("BUY", "SELL")


def validate_symbol(symbol: str) -> str:
    """
    Normalise and basic-validate a trading symbol.

    Rules:
    - Must be a non-empty alphabetic string (e.g. BTCUSDT).
    - Converted to upper-case automatically.

    Args:
        symbol: Raw symbol string from user input.

    Returns:
        Upper-cased symbol string.

    Raises:
        ValueError: If the symbol is empty or contains non-alphabetic characters.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    if not symbol.isalpha():
        raise ValueError(
            f"Symbol '{symbol}' is invalid. Use only letters, e.g. BTCUSDT."
        )
    return symbol


def validate_side(side: str) -> str:
    """
    Validate and normalise the order side.

    Args:
        side: Raw side string from user input ('buy', 'SELL', etc.).

    Returns:
        Upper-cased side string ('BUY' or 'SELL').

    Raises:
        ValueError: If side is not BUY or SELL.
    """
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(VALID_SIDES)}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """
    Validate and normalise the order type.

    Supported types:
    - MARKET      : Execute immediately at best available price.
    - LIMIT       : Execute at specified price or better (requires --price).
    - STOP_MARKET : Trigger a market order when price hits stop (requires --stop-price).
    - STOP        : Trigger a limit order when price hits stop (requires both
                    --stop-price and --price). This is a Stop-Limit order.

    Args:
        order_type: Raw order type from user input.

    Returns:
        Upper-cased order type string.

    Raises:
        ValueError: If order type is not supported.
    """
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(VALID_ORDER_TYPES)}."
        )
    return order_type


def validate_quantity(quantity: str) -> str:
    """
    Validate that the quantity is a positive decimal number.

    Args:
        quantity: Raw quantity string from user input.

    Returns:
        Validated quantity string (kept as string to preserve precision).

    Raises:
        ValueError: If quantity is not a valid positive number.
    """
    try:
        qty = Decimal(str(quantity).strip())
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a numeric value.")

    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero. Got: {qty}.")

    return str(qty)


def validate_price(price: Optional[str], order_type: str) -> Optional[str]:
    """
    Validate the price argument given the order type.

    Rules:
    - LIMIT orders REQUIRE a price.
    - STOP_MARKET orders REQUIRE a stop price (validated separately via --stop-price).
    - MARKET orders must NOT supply a price.

    Args:
        price: Raw price string from user input (may be None).
        order_type: Already-validated order type string.

    Returns:
        Validated price string, or None for MARKET orders.

    Raises:
        ValueError: On missing price for LIMIT, or unexpected price for MARKET.
    """
    if order_type == "LIMIT":
        if price is None:
            raise ValueError("A --price is required for LIMIT orders.")
        try:
            p = Decimal(str(price).strip())
        except InvalidOperation:
            raise ValueError(f"Invalid price '{price}'. Must be a numeric value.")
        if p <= 0:
            raise ValueError(f"Price must be greater than zero. Got: {p}.")
        return str(p)

    if order_type == "STOP":
        # Stop-Limit order: requires BOTH --stop-price and --price (the limit price)
        if price is None:
            raise ValueError(
                "A --price (limit price) is required for STOP (stop-limit) orders. "
                "This is the price at which the limit order will be placed after the "
                "stop is triggered."
            )
        try:
            p = Decimal(str(price).strip())
        except InvalidOperation:
            raise ValueError(f"Invalid price '{price}'. Must be a numeric value.")
        if p <= 0:
            raise ValueError(f"Price must be greater than zero. Got: {p}.")
        return str(p)

    if order_type == "MARKET":
        if price is not None:
            raise ValueError(
                "Price is not applicable for MARKET orders. Remove --price."
            )
        return None

    # STOP_MARKET: price param not used (stop_price validated separately)
    return None


def validate_stop_price(stop_price: Optional[str], order_type: str) -> Optional[str]:
    """
    Validate the stop price for STOP_MARKET orders.

    Args:
        stop_price: Raw stop price string from user input.
        order_type: Already-validated order type string.

    Returns:
        Validated stop price string, or None if not applicable.

    Raises:
        ValueError: If STOP_MARKET order is missing a stop price.
    """
    if order_type in ("STOP_MARKET", "STOP"):
        if stop_price is None:
            label = "STOP_MARKET" if order_type == "STOP_MARKET" else "STOP (stop-limit)"
            raise ValueError(f"A --stop-price is required for {label} orders.")
        try:
            sp = Decimal(str(stop_price).strip())
        except InvalidOperation:
            raise ValueError(
                f"Invalid stop price '{stop_price}'. Must be a numeric value."
            )
        if sp <= 0:
            raise ValueError(f"Stop price must be greater than zero. Got: {sp}.")
        return str(sp)

    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> dict:
    """
    Run all validators and return a clean, normalised parameter dictionary.

    Args:
        symbol:      Trading pair symbol (e.g. 'BTCUSDT').
        side:        Order side ('BUY' or 'SELL').
        order_type:  Order type ('MARKET', 'LIMIT', 'STOP_MARKET').
        quantity:    Order quantity as string.
        price:       Limit price as string (LIMIT orders only).
        stop_price:  Stop price as string (STOP_MARKET orders only).

    Returns:
        Dictionary with validated and normalised values.

    Raises:
        ValueError: On any validation failure.
    """
    v_symbol = validate_symbol(symbol)
    v_side = validate_side(side)
    v_type = validate_order_type(order_type)
    v_qty = validate_quantity(quantity)
    v_price = validate_price(price, v_type)
    v_stop = validate_stop_price(stop_price, v_type)

    return {
        "symbol": v_symbol,
        "side": v_side,
        "order_type": v_type,
        "quantity": v_qty,
        "price": v_price,
        "stop_price": v_stop,
    }
