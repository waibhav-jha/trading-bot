# bot/interactive.py
"""
Interactive menu-driven UX for the trading bot.

Launched when `python cli.py` is called with no arguments.
Guides the user through order placement with inline validation,
colour-coded prompts, and a confirmation step before submission.
"""

import sys
from decimal import Decimal, InvalidOperation
from typing import Optional

from bot.validators import VALID_ORDER_TYPES, VALID_SIDES

# ── ANSI colour helpers (gracefully degraded on Windows without ANSI support) ─

def _supports_color() -> bool:
    """Return True if the terminal likely supports ANSI escape codes."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def green(t: str)  -> str: return _c(t, "32")
def yellow(t: str) -> str: return _c(t, "33")
def red(t: str)    -> str: return _c(t, "31")
def cyan(t: str)   -> str: return _c(t, "36")
def bold(t: str)   -> str: return _c(t, "1")
def dim(t: str)    -> str: return _c(t, "2")


# ── Low-level prompt helpers ─────────────────────────────────────────────────

def _prompt(label: str, hint: str = "") -> str:
    """Display a styled prompt and return stripped user input."""
    hint_str = f"  {dim(hint)}" if hint else ""
    try:
        return input(f"  {cyan('›')} {bold(label)}{hint_str}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n\n{yellow('Aborted.')} No order was placed.\n")
        sys.exit(0)


def _prompt_choice(label: str, choices: tuple, hint: str = "") -> str:
    """
    Prompt until the user enters one of the allowed choices (case-insensitive).
    Returns the normalised upper-case choice.
    """
    options = " / ".join(f"{bold(c)}" for c in choices)
    hint_full = f"[{options}]" + (f"  {dim(hint)}" if hint else "")
    while True:
        raw = _prompt(label, hint_full)
        if raw.upper() in choices:
            return raw.upper()
        print(f"    {red('✗')} Please enter one of: {', '.join(choices)}")


def _prompt_positive_decimal(label: str, hint: str = "") -> str:
    """Prompt until the user enters a positive decimal number."""
    while True:
        raw = _prompt(label, hint)
        try:
            val = Decimal(raw)
            if val <= 0:
                raise ValueError
            return str(val)
        except (InvalidOperation, ValueError):
            print(f"    {red('✗')} Must be a positive number (e.g. 0.001). Try again.")


def _prompt_optional_decimal(label: str, hint: str = "") -> Optional[str]:
    """Prompt for an optional decimal; returns None if the user presses Enter."""
    while True:
        raw = _prompt(label, hint + "  (press Enter to skip)")
        if raw == "":
            return None
        try:
            val = Decimal(raw)
            if val <= 0:
                raise ValueError
            return str(val)
        except (InvalidOperation, ValueError):
            print(f"    {red('✗')} Must be a positive number or blank. Try again.")


# ── Section header ────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    width = 54
    print()
    print(cyan("─" * width))
    print(f"  {bold(title)}")
    print(cyan("─" * width))


# ── Main interactive flow ─────────────────────────────────────────────────────

def run_interactive() -> dict:
    """
    Run the full interactive order-entry flow.

    Displays a menu, collects validated inputs step-by-step, shows a
    confirmation summary, and returns a validated parameter dict identical
    in shape to what `validate_all()` produces — ready to pass to
    `execute_order()`.

    Returns:
        Dict with keys: symbol, side, order_type, quantity, price, stop_price.

    Raises:
        SystemExit: If the user aborts at any point or declines confirmation.
    """
    # ── Welcome banner ───────────────────────────────────────────────────────
    print()
    print(bold(cyan("╔══════════════════════════════════════════════════════╗")))
    print(bold(cyan("║       BINANCE FUTURES TESTNET  ·  TRADING BOT       ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════════╝")))
    print(dim("  Interactive order entry  |  Ctrl-C to abort at any time"))

    # ── Order type menu ──────────────────────────────────────────────────────
    _section("ORDER TYPE")
    print(f"    {bold('1')}  MARKET      — fill immediately at best price")
    print(f"    {bold('2')}  LIMIT       — fill at your specified price or better")
    print(f"    {bold('3')}  STOP_MARKET — market order triggered at stop price")
    print(f"    {bold('4')}  STOP        — stop-limit (limit order triggered at stop price)")
    print()

    _type_map = {"1": "MARKET", "2": "LIMIT", "3": "STOP_MARKET", "4": "STOP"}
    while True:
        raw = _prompt("Select type", "[1 / 2 / 3 / 4]")
        if raw in _type_map:
            order_type = _type_map[raw]
            print(f"    {green('✓')} {order_type} selected")
            break
        # Also accept the type name directly
        if raw.upper() in VALID_ORDER_TYPES:
            order_type = raw.upper()
            print(f"    {green('✓')} {order_type} selected")
            break
        print(f"    {red('✗')} Enter a number 1–4 or the order type name.")

    # ── Symbol ───────────────────────────────────────────────────────────────
    _section("SYMBOL")
    while True:
        symbol = _prompt("Trading pair", "e.g. BTCUSDT, ETHUSDT").upper()
        if symbol and symbol.isalpha():
            print(f"    {green('✓')} {symbol}")
            break
        print(f"    {red('✗')} Symbol must contain only letters (e.g. BTCUSDT).")

    # ── Side ─────────────────────────────────────────────────────────────────
    _section("SIDE")
    side = _prompt_choice("Direction", VALID_SIDES)
    print(f"    {green('✓')} {side}")

    # ── Quantity ─────────────────────────────────────────────────────────────
    _section("QUANTITY")
    quantity = _prompt_positive_decimal("Quantity", "e.g. 0.001")
    print(f"    {green('✓')} {quantity}")

    # ── Price fields (conditional on order type) ──────────────────────────────
    price: Optional[str] = None
    stop_price: Optional[str] = None

    if order_type == "LIMIT":
        _section("LIMIT PRICE")
        price = _prompt_positive_decimal("Limit price", "order fills at this price or better")
        print(f"    {green('✓')} {price}")

    elif order_type == "STOP_MARKET":
        _section("STOP PRICE")
        print(dim("  A market order fires when the price reaches this level."))
        stop_price = _prompt_positive_decimal("Stop price", "trigger level")
        print(f"    {green('✓')} {stop_price}")

    elif order_type == "STOP":
        _section("STOP-LIMIT PRICES")
        print(dim("  When market hits Stop Price → a Limit order at Limit Price is placed."))
        stop_price = _prompt_positive_decimal("Stop price ", "trigger level")
        print(f"    {green('✓')} stop trigger: {stop_price}")
        price = _prompt_positive_decimal("Limit price", "limit fill price after trigger")
        print(f"    {green('✓')} limit price : {price}")

    # ── Confirmation summary ─────────────────────────────────────────────────
    print()
    print(bold(cyan("══════════════════════════════════════════════════════")))
    print(bold("  CONFIRM ORDER"))
    print(bold(cyan("══════════════════════════════════════════════════════")))
    print(f"  Symbol     : {bold(symbol)}")
    print(f"  Side       : {bold(green(side) if side == 'BUY' else bold(red(side)))}")
    print(f"  Type       : {bold(order_type)}")
    print(f"  Quantity   : {bold(quantity)}")
    if price:
        print(f"  Limit Price: {bold(price)}")
    if stop_price:
        print(f"  Stop Price : {bold(stop_price)}")
    print(bold(cyan("══════════════════════════════════════════════════════")))
    print()

    confirm = _prompt_choice(
        "Submit this order?",
        ("YES", "NO"),
        hint="YES to place  /  NO to abort",
    )
    if confirm != "YES":
        print(f"\n{yellow('Aborted.')} No order was placed.\n")
        sys.exit(0)

    print(f"\n  {green('Submitting…')}\n")

    return {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price,
        "stop_price": stop_price,
    }
