#!/usr/bin/env python3
# cli.py
"""
Command-line entry point for the Binance Futures Testnet trading bot.

Two modes of operation:
  1. Direct (flags provided) — fast, scriptable, CI-friendly.
  2. Interactive (no flags)  — guided menu with inline validation.

Usage examples:
  python cli.py                                                        # interactive
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 58000
  python cli.py --symbol BTCUSDT --side BUY  --type STOP --quantity 0.001 --stop-price 62000 --price 62500
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from bot.client import BinanceAPIError, BinanceClient
from bot.interactive import run_interactive
from bot.logging_config import setup_logging
from bot.orders import execute_order
from bot.validators import VALID_ORDER_TYPES, VALID_SIDES, validate_all

# ── Bootstrap ────────────────────────────────────────────────────────────────

load_dotenv()
logger = setup_logging()


# ── CLI argument parser ──────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description=(
            "Binance Futures Testnet Trading Bot\n"
            "────────────────────────────────────\n"
            "Run with NO arguments to enter interactive menu mode.\n"
            "Pass flags directly for scriptable / non-interactive use.\n\n"
            "Order types:\n"
            "  MARKET      – fill immediately at best available price\n"
            "  LIMIT       – fill at specified price or better  (--price required)\n"
            "  STOP_MARKET – market order triggered at stop price (--stop-price required)\n"
            "  STOP        – stop-limit order  (--stop-price AND --price required)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cli.py\n"
            "  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001\n"
            "  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500\n"
            "  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 58000\n"
            "  python cli.py --symbol BTCUSDT --side BUY  --type STOP --quantity 0.001 --stop-price 62000 --price 62500\n"
        ),
    )
    parser.add_argument("--symbol",     default=None, metavar="SYMBOL")
    parser.add_argument("--side",       default=None, choices=VALID_SIDES, metavar="SIDE")
    parser.add_argument("--type",       dest="order_type", default=None, choices=VALID_ORDER_TYPES, metavar="TYPE")
    parser.add_argument("--quantity",   default=None, metavar="QTY")
    parser.add_argument("--price",      default=None, metavar="PRICE")
    parser.add_argument("--stop-price", dest="stop_price", default=None, metavar="STOP_PRICE")
    return parser


# ── Print helpers ─────────────────────────────────────────────────────────────

def print_order_summary(params: dict) -> None:
    print()
    print("=" * 54)
    print("  ORDER REQUEST SUMMARY")
    print("=" * 54)
    print(f"  Symbol     : {params['symbol']}")
    print(f"  Side       : {params['side']}")
    print(f"  Type       : {params['order_type']}")
    print(f"  Quantity   : {params['quantity']}")
    if params.get("price"):
        label = "Limit Price" if params["order_type"] in ("LIMIT", "STOP") else "Price"
        print(f"  {label:<11}: {params['price']}")
    if params.get("stop_price"):
        print(f"  Stop Price : {params['stop_price']}")
    print("=" * 54)
    print()


# ── Credential loading ────────────────────────────────────────────────────────

def load_credentials():
    api_key    = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        msg = (
            "BINANCE_API_KEY and BINANCE_API_SECRET must be set.\n"
            "Create a .env file in the project root or export them as shell variables."
        )
        logger.error(msg)
        print(f"\n[ERROR] {msg}\n", file=sys.stderr)
        sys.exit(1)
    return api_key, api_secret


# ── Order submission ──────────────────────────────────────────────────────────

def submit_order(validated: dict) -> None:
    """Place the order and print results. Shared by both CLI modes."""
    logger.info("Validated order parameters: %s", validated)
    api_key, api_secret = load_credentials()

    try:
        client = BinanceClient(api_key=api_key, api_secret=api_secret)
    except ValueError as exc:
        logger.error("Client init failed: %s", exc)
        print(f"\n[ERROR] {exc}\n", file=sys.stderr)
        sys.exit(1)

    try:
        _response, formatted = execute_order(
            client=client,
            symbol=validated["symbol"],
            side=validated["side"],
            order_type=validated["order_type"],
            quantity=validated["quantity"],
            price=validated.get("price"),
            stop_price=validated.get("stop_price"),
        )
    except BinanceAPIError as exc:
        logger.error("Binance API error | code=%s msg=%s", exc.code, exc.message)
        print(f"\n[ERROR] Binance API returned an error: {exc}\n", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as exc:
        logger.error("Network error: %s", exc)
        print(f"\n[ERROR] Network failure: {exc}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while placing order: %s", exc)
        print(f"\n[ERROR] Unexpected error: {exc}\n", file=sys.stderr)
        sys.exit(1)

    print(formatted)
    print("[OK] Order submitted successfully.\n")
    logger.info("Order submission complete.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    direct_mode = any([args.symbol, args.side, args.order_type, args.quantity])

    if not direct_mode:
        # ── INTERACTIVE MODE ─────────────────────────────────────────────────
        logger.info("Launching interactive mode")
        validated = run_interactive()
        print_order_summary(validated)
        submit_order(validated)

    else:
        # ── DIRECT / FLAG MODE ───────────────────────────────────────────────
        missing = [
            name for name, val in [
                ("--symbol",   args.symbol),
                ("--side",     args.side),
                ("--type",     args.order_type),
                ("--quantity", args.quantity),
            ] if not val
        ]
        if missing:
            parser.error(
                f"Missing required flags in direct mode: {', '.join(missing)}\n"
                "  Tip: run `python cli.py` with no arguments for interactive mode."
            )

        logger.info(
            "Direct mode | symbol=%s side=%s type=%s qty=%s price=%s stop_price=%s",
            args.symbol, args.side, args.order_type,
            args.quantity, args.price, args.stop_price,
        )

        try:
            validated = validate_all(
                symbol=args.symbol,
                side=args.side,
                order_type=args.order_type,
                quantity=args.quantity,
                price=args.price,
                stop_price=args.stop_price,
            )
        except ValueError as exc:
            logger.error("Input validation failed: %s", exc)
            print(f"\n[ERROR] Invalid input: {exc}\n", file=sys.stderr)
            sys.exit(1)

        print_order_summary(validated)
        submit_order(validated)


if __name__ == "__main__":
    main()
