# bot/orders.py
"""
Order-placement logic for the Binance Futures Testnet trading bot.

This module acts as the business-logic layer sitting between the CLI (cli.py)
and the raw API client (client.py).  It translates validated user parameters
into the exact payload Binance expects, then formats the response for display.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from bot.client import BinanceClient

logger = logging.getLogger("trading_bot.orders")


# ── Internal helpers ─────────────────────────────────────────────────────────

def _build_order_payload(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construct the raw Binance API order payload from validated parameters.

    Args:
        symbol:     Trading pair, e.g. 'BTCUSDT'.
        side:       'BUY' or 'SELL'.
        order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET'.
        quantity:   Order quantity as a string (preserves decimal precision).
        price:      Limit price string (LIMIT orders only).
        stop_price: Stop trigger price string (STOP_MARKET orders only).

    Returns:
        Dict ready to pass to BinanceClient.place_order().
    """
    payload: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
    }

    if order_type == "LIMIT":
        payload["price"] = price
        # GTC = Good Till Cancelled; required for LIMIT orders on Binance Futures
        payload["timeInForce"] = "GTC"

    elif order_type == "STOP":
        # Stop-Limit: stopPrice triggers the order; price is the limit fill price
        payload["stopPrice"] = stop_price
        payload["price"] = price
        payload["timeInForce"] = "GTC"

    elif order_type == "STOP_MARKET":
        payload["stopPrice"] = stop_price
        # closePosition=false means we're opening / partially closing a position
        payload["closePosition"] = "false"

    logger.debug("Built order payload: %s", payload)
    return payload


def _format_response(response: Dict[str, Any]) -> str:
    """
    Format the Binance order response into a human-readable summary string.

    Args:
        response: Raw dict from the Binance API.

    Returns:
        Multi-line formatted string suitable for printing to the console.
    """
    order_id   = response.get("orderId", response.get("algoId", "N/A"))
    client_id  = response.get("clientOrderId", response.get("clientAlgoId", "N/A"))
    symbol     = response.get("symbol", "N/A")
    side       = response.get("side", "N/A")
    otype      = response.get("type", response.get("orderType", "N/A"))
    status     = response.get("status", response.get("algoStatus", "N/A"))
    orig_qty   = response.get("origQty", response.get("quantity", "N/A"))
    exec_qty   = response.get("executedQty", response.get("executedQty", "N/A"))
    avg_price  = response.get("avgPrice", "N/A")
    price      = response.get("price", "N/A")
    stop_price = response.get("stopPrice", response.get("triggerPrice", "N/A"))
    time_ms    = response.get("updateTime", "N/A")

    lines = [
        "",
        "=" * 54,
        "  ORDER RESPONSE",
        "=" * 54,
        f"  Order ID       : {order_id}",
        f"  Client ID      : {client_id}",
        f"  Symbol         : {symbol}",
        f"  Side           : {side}",
        f"  Type           : {otype}",
        f"  Status         : {status}",
        f"  Original Qty   : {orig_qty}",
        f"  Executed Qty   : {exec_qty}",
        f"  Avg Fill Price : {avg_price}",
    ]

    if otype == "LIMIT":
        lines.append(f"  Limit Price    : {price}")
    if otype in ("STOP_MARKET", "STOP"):
        lines.append(f"  Stop Price     : {stop_price}")
    if otype == "STOP":
        lines.append(f"  Limit Price    : {price}")

    lines += [
        f"  Update Time    : {time_ms} ms",
        "=" * 54,
        "",
    ]
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────────────

def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: str,
) -> Dict[str, Any]:
    """
    Place a MARKET order on Binance Futures Testnet.

    Args:
        client:   Authenticated BinanceClient instance.
        symbol:   Trading pair symbol, e.g. 'BTCUSDT'.
        side:     'BUY' or 'SELL'.
        quantity: Order quantity.

    Returns:
        Binance API response dict.
    """
    logger.info(
        "Placing MARKET order | symbol=%s side=%s qty=%s",
        symbol, side, quantity,
    )
    payload = _build_order_payload(symbol, side, "MARKET", quantity)
    response = client.place_order(payload)
    logger.info("MARKET order placed successfully | orderId=%s", response.get("orderId"))
    return response


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: str,
    price: str,
) -> Dict[str, Any]:
    """
    Place a LIMIT order on Binance Futures Testnet.

    Args:
        client:   Authenticated BinanceClient instance.
        symbol:   Trading pair symbol.
        side:     'BUY' or 'SELL'.
        quantity: Order quantity.
        price:    Limit price.

    Returns:
        Binance API response dict.
    """
    logger.info(
        "Placing LIMIT order | symbol=%s side=%s qty=%s price=%s",
        symbol, side, quantity, price,
    )
    payload = _build_order_payload(symbol, side, "LIMIT", quantity, price=price)
    response = client.place_order(payload)
    logger.info("LIMIT order placed successfully | orderId=%s", response.get("orderId"))
    return response


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: str,
    stop_price: str,
    price: str,
) -> Dict[str, Any]:
    """
    Place a STOP (stop-limit) order on Binance Futures Testnet.

    When the market price reaches `stop_price`, a limit order at `price`
    is automatically placed.  Useful for entering positions on breakouts
    or exiting with a guaranteed limit price rather than a market fill.

    Args:
        client:     Authenticated BinanceClient instance.
        symbol:     Trading pair symbol.
        side:       'BUY' or 'SELL'.
        quantity:   Order quantity.
        stop_price: Price that triggers placement of the limit order.
        price:      Limit price for the order placed after trigger.

    Returns:
        Binance API response dict.
    """
    logger.info(
        "Placing STOP-LIMIT order | symbol=%s side=%s qty=%s stopPrice=%s limitPrice=%s",
        symbol, side, quantity, stop_price, price,
    )
    payload = _build_order_payload(
        symbol, side, "STOP", quantity, price=price, stop_price=stop_price
    )
    response = client.place_order(payload)
    logger.info(
        "STOP-LIMIT order placed successfully | orderId=%s", response.get("orderId")
    )
    return response


def place_stop_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: str,
    stop_price: str,
) -> Dict[str, Any]:
    """
    Place a STOP_MARKET order on Binance Futures Testnet.

    A STOP_MARKET order triggers a market order when the price reaches
    the specified stop price.  Useful for stop-loss placement.

    Args:
        client:     Authenticated BinanceClient instance.
        symbol:     Trading pair symbol.
        side:       'BUY' or 'SELL'.
        quantity:   Order quantity.
        stop_price: Price that triggers the market order.

    Returns:
        Binance API response dict.
    """
    logger.info(
        "Placing STOP_MARKET order | symbol=%s side=%s qty=%s stopPrice=%s",
        symbol, side, quantity, stop_price,
    )
    payload = _build_order_payload(
        symbol, side, "STOP_MARKET", quantity, stop_price=stop_price
    )
    response = client.place_order(payload)
    logger.info(
        "STOP_MARKET order placed successfully | orderId=%s", response.get("orderId")
    )
    return response


def execute_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Dispatch to the correct order-placement function based on order_type.

    This is the single entry-point called by the CLI layer.

    Args:
        client:     Authenticated BinanceClient instance.
        symbol:     Trading pair symbol.
        side:       'BUY' or 'SELL'.
        order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET'.
        quantity:   Order quantity.
        price:      Limit price (LIMIT orders).
        stop_price: Stop trigger price (STOP_MARKET orders).

    Returns:
        Tuple of (response dict, formatted response string).

    Raises:
        ValueError: If an unsupported order_type is supplied (shouldn't happen
                    after validation, but kept as a safety net).
    """
    if order_type == "MARKET":
        response = place_market_order(client, symbol, side, quantity)
    elif order_type == "LIMIT":
        response = place_limit_order(client, symbol, side, quantity, price)  # type: ignore[arg-type]
    elif order_type == "STOP_MARKET":
        response = place_stop_market_order(client, symbol, side, quantity, stop_price)  # type: ignore[arg-type]
    elif order_type == "STOP":
        response = place_stop_limit_order(client, symbol, side, quantity, stop_price, price)  # type: ignore[arg-type]
    else:
        raise ValueError(f"Unsupported order type: {order_type}")

    formatted = _format_response(response)
    return response, formatted
