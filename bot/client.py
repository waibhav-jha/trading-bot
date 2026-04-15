# bot/client.py
"""
Binance Futures Testnet REST API client.

Handles:
- HMAC-SHA256 request signing
- Authenticated GET / POST requests
- Centralised error parsing and raising
- Retry on transient network failures
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("trading_bot.client")

# ── Constants ────────────────────────────────────────────────────────────────
BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000  # milliseconds; max clock drift the server will accept


class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-2xx response or error body."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    All public methods return the parsed JSON response body as a dict.
    Network and API errors are surfaced as exceptions (never swallowed).
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        """
        Initialise the client with API credentials.

        Args:
            api_key:    Your Binance Testnet API key.
            api_secret: Your Binance Testnet API secret.
        """
        if not api_key or not api_secret:
            raise ValueError(
                "API key and secret must be non-empty strings. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file."
            )

        self._api_key = api_key
        self._api_secret = api_secret.encode()  # bytes required for HMAC

        # Build a session with automatic retry on transient failures
        self._session = self._build_session()
        logger.debug("BinanceClient initialised (base_url=%s)", BASE_URL)

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        """Return a requests.Session with retry logic pre-configured."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        return session

    def _sign(self, params: Dict[str, Any]) -> str:
        """
        Generate the HMAC-SHA256 signature for a parameter dictionary.

        Args:
            params: Query / body parameters (must include 'timestamp').

        Returns:
            Hex-encoded signature string.
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret, query_string.encode(), hashlib.sha256
        ).hexdigest()
        logger.debug("Signed params: %s → signature: %s…", query_string[:80], signature[:16])
        return signature

    @staticmethod
    def _timestamp() -> int:
        """Return current UTC time in milliseconds."""
        return int(time.time() * 1000)

    def _headers(self) -> Dict[str, str]:
        """Return headers required by Binance signed endpoints."""
        return {
            "X-MBX-APIKEY": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parse an HTTP response, raising on error.

        Args:
            response: The raw requests.Response object.

        Returns:
            Parsed JSON body as a dictionary.

        Raises:
            BinanceAPIError: If the API returned an error payload.
            requests.HTTPError: For unexpected HTTP status codes.
        """
        logger.debug(
            "HTTP %s %s → status=%d",
            response.request.method,
            response.url,
            response.status_code,
        )

        try:
            body = response.json()
        except ValueError:
            response.raise_for_status()
            return {}

        # Binance error responses have a 'code' key that is negative
        if isinstance(body, dict) and "code" in body and body["code"] != 200:
            err_code = body.get("code", -1)
            err_msg = body.get("msg", "Unknown error")
            logger.error("Binance API error: code=%s msg=%s", err_code, err_msg)
            raise BinanceAPIError(err_code, err_msg)

        if not response.ok:
            response.raise_for_status()

        logger.debug("Response body: %s", body)
        return body

    # ── Public API methods ───────────────────────────────────────────────────

    def get_server_time(self) -> Dict[str, Any]:
        """Fetch server time (useful for clock-sync checks). Unsigned endpoint."""
        url = f"{BASE_URL}/fapi/v1/time"
        logger.debug("GET %s", url)
        resp = self._session.get(url, timeout=10)
        return self._handle_response(resp)

    def get_exchange_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch exchange trading rules for a symbol. Unsigned endpoint."""
        url = f"{BASE_URL}/fapi/v1/exchangeInfo"
        logger.debug("GET %s (symbol=%s)", url, symbol)
        resp = self._session.get(url, params={"symbol": symbol}, timeout=10)
        return self._handle_response(resp)

    def get_account_balance(self) -> Dict[str, Any]:
        """Fetch account balance. Signed endpoint."""
        params: Dict[str, Any] = {
            "timestamp": self._timestamp(),
            "recvWindow": RECV_WINDOW,
        }
        params["signature"] = self._sign(params)
        url = f"{BASE_URL}/fapi/v2/balance"
        logger.debug("GET %s", url)
        resp = self._session.get(
            url, params=params, headers=self._headers(), timeout=10
        )
        return self._handle_response(resp)

    def place_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a new futures order.

        Args:
            order_params: Dict containing at minimum:
                - symbol (str)
                - side   ('BUY' | 'SELL')
                - type   ('MARKET' | 'LIMIT' | 'STOP_MARKET')
                - quantity (str)
                - Additional keys depending on order type
                  (e.g. price, timeInForce, stopPrice).

        Returns:
            Binance order response dict.

        Raises:
            BinanceAPIError: On API-level errors.
            requests.RequestException: On network failures.
        """
        params: Dict[str, Any] = {
            **order_params,
            "timestamp": self._timestamp(),
            "recvWindow": RECV_WINDOW,
        }

        algo_types = {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET"}
        if params.get("type") in algo_types:
            params["algoType"] = "CONDITIONAL"
            url = f"{BASE_URL}/fapi/v1/algoOrder"
            if "stopPrice" in params:
                params["triggerPrice"] = params.pop("stopPrice")
        else:
            url = f"{BASE_URL}/fapi/v1/order"

        params["signature"] = self._sign(params)

        logger.info("POST %s | params=%s", url, {k: v for k, v in params.items() if k != "signature"})

        resp = self._session.post(
            url,
            data=params,       # Binance expects form-encoded body for POST
            headers=self._headers(),
            timeout=15,
        )
        result = self._handle_response(resp)
        logger.info("Order response: %s", result)
        return result
