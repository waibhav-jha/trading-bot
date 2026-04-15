# Binance Futures Testnet Trading Bot

A clean, production-quality Python CLI application that places **MARKET**, **LIMIT**, and **STOP_MARKET** orders on the [Binance Futures USDT-M Testnet](https://testnet.binancefuture.com) using standard endpoints and the new Algo Order endpoints for conditional orders.

---

## Features

- ✅ **Market orders** — execute immediately at the best available price
- ✅ **Limit orders** — execute only at a specified price or better
- ✅ **Stop-Market orders** — trigger a market order when price reaches a stop level
- ✅ **Stop-Limit orders** — trigger a limit order when the price hits the stop level
- ✅ Structured logging to a timestamped `.log` file + console
- ✅ Full input validation with descriptive error messages
- ✅ Automatic routing of Conditional (Algo) Orders natively
- ✅ Retry logic for transient network failures
- ✅ Credentials loaded securely via environment variables / `.env`
- ✅ Web Interface over local proxy server to avoid CORS blocks

---

## Setup Steps

### 1. Obtain Binance Futures Testnet credentials
1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com) and log in with your account.
2. Navigate to **API Management** and generate a new API key + secret.
3. Keep both values handy for the next step.

### 2. Clone / download the project
```bash
git clone <repo-url>
cd trading_bot
```

### 3. Create a virtual environment and install dependencies
```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 4. Configure API credentials
Copy the example env file and fill in your testnet credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```dotenv
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```
> **Never commit your `.env` file to version control.**

---

## How to Run Examples

All commands must be run from the root directory with the virtual environment active.

### General syntax
```bash
python cli.py --symbol SYMBOL --side SIDE --type TYPE --quantity QTY [--price PRICE] [--stop-price STOP_PRICE]
```

### Placed Orders (Runnable Instructions)

**1. Place a MARKET BUY order**
```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

**2. Place a LIMIT SELL order**
```bash
python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3500
```

**3. Place a STOP_MARKET SELL order (Stop-Loss)**  
*(Ensures your sell triggers cleanly onto the market if the price falls past your target).*
```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.002 --stop-price 55000
```

**4. Place a STOP BUY order (Stop-Limit)**  
*(Wait for a breakout: if BTC breaks above 90,000, place a limit buy at 90,500).*
```bash
python cli.py --symbol BTCUSDT --side BUY --type STOP --quantity 0.002 --stop-price 90000 --price 90500
```
> *Note: By Binance Futures rules, `BUY STOP` orders must have a trigger strictly above the current market price, and the total notional value (Price x Quantity) must exceed $100 USDT.*

---

## Interactive Menu Mode
If you prefer not to use CLI flags, run the prompt without any arguments:
```bash
python cli.py
```
This loads a guided interface with inline validation and confirmation prompts.

---

## Web UI (`ui.html`)
To run the lightweight browser interface properly and bypass Binance API Browser CORS blocks, you must use the included proxy.

**1. Start the proxy server:**
```bash
python server.py
```

**2. Open your browser and navigate to:**
[http://localhost:8000/ui.html](http://localhost:8000/ui.html)

---

## Assumptions

1. **Testnet ONLY** — the base URL is hard-coded to `https://testnet.binancefuture.com`. For mainnet use, change `BASE_URL` in `bot/client.py`.
2. **USDT-M Futures** — all orders target the USDⓈ-M perpetual futures market.
3. **No Position Management** — the bot places orders only; position tracking and PnL calculation are out of scope.
4. **Quantity Precision & Minimums** — the caller is responsible for providing a quantity that satisfies Binance's `LOT_SIZE` filter and meets the minimum $100 equivalent notional value size per order.
5. **Clock Synchronisation** — the bot uses a 5,000 ms `recvWindow`. If your system clock drifts more than ±5 s from UTC, requests may be rejected with error `-1021`. 
6. **Binance API Endpoints** — Standard orders use `/fapi/v1/order`. Conditional orders (`STOP`, `STOP_MARKET`) automatically route to the newer `/fapi/v1/algoOrder` endpoint as required by Binance.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing required argument | `argparse` prints usage and exits |
| Binance API error (e.g. -4164) | `BinanceAPIError` caught, message and API explanation printed safely |
| Missing price/trigger | Validator rejects via `ValueError` |
| Network timeout / refusal | Caught `requests.RequestException` |
