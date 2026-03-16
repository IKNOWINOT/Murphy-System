"""
Yahoo Finance Market Data Integration — Murphy System World Model Connector.

Uses Yahoo Finance public APIs (no API key required — free).
Primary path: yfinance library (if installed, `pip install yfinance`).
HTTP fallback: Yahoo Finance public JSON endpoints (query1.finance.yahoo.com).
Setup: No setup required — free public data.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector

logger = logging.getLogger(__name__)



class YahooFinanceConnector(BaseIntegrationConnector):
    """Yahoo Finance connector — free market data, no API key required."""

    INTEGRATION_NAME = "Yahoo Finance"
    BASE_URL = "https://query1.finance.yahoo.com"
    CREDENTIAL_KEYS = []  # No credentials required
    REQUIRED_CREDENTIALS = []
    FREE_TIER = True
    SETUP_URL = ""
    DOCUMENTATION_URL = "https://pypi.org/project/yfinance/"

    def is_configured(self) -> bool:
        return True  # Always configured — no credentials needed

    def _build_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Murphy-System/1.0; +https://murphysystem.com)",
            "Accept": "application/json",
        }

    # -- Try yfinance library first, fall back to HTTP --

    def _try_yfinance(self, method: str, **kwargs) -> Optional[Any]:
        """Attempt to use the yfinance library."""
        try:
            import yfinance as yf  # type: ignore[import]
            return getattr(yf, method)(**kwargs)
        except ImportError:
            return None
        except Exception as exc:
            return None

    # -- Quote / Price --

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for a ticker symbol."""
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                info = ticker.info
                return {"success": True, "configured": True, "simulated": False,
                        "data": info, "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        # HTTP fallback
        result = self._get("/v8/finance/quote",
                           params={"symbols": symbol,
                                   "fields": "symbol,regularMarketPrice,regularMarketChange,"
                                             "regularMarketChangePercent,marketCap,volume,"
                                             "fiftyTwoWeekHigh,fiftyTwoWeekLow"})
        return result

    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        return self._get("/v8/finance/quote",
                         params={"symbols": ",".join(symbols)})

    def get_history(self, symbol: str, period: str = "1mo",
                    interval: str = "1d") -> Dict[str, Any]:
        """Get historical price data. period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max"""
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                hist = ticker.history(period=period, interval=interval)
                return {"success": True, "configured": True, "simulated": False,
                        "data": hist.to_dict() if hasattr(hist, "to_dict") else {},
                        "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        # HTTP fallback
        return self._get(f"/v8/finance/chart/{symbol}",
                         params={"range": period, "interval": interval})

    def get_financials(self, symbol: str) -> Dict[str, Any]:
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                return {"success": True, "configured": True, "simulated": False,
                        "data": {
                            "income_statement": ticker.financials.to_dict() if hasattr(ticker.financials, "to_dict") else {},
                            "balance_sheet": ticker.balance_sheet.to_dict() if hasattr(ticker.balance_sheet, "to_dict") else {},
                            "cash_flow": ticker.cashflow.to_dict() if hasattr(ticker.cashflow, "to_dict") else {},
                        }, "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        return self._get(f"/v8/finance/chart/{symbol}",
                         params={"modules": "financialData,incomeStatementHistory"})

    def get_summary(self, symbol: str) -> Dict[str, Any]:
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                return {"success": True, "configured": True, "simulated": False,
                        "data": ticker.info, "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        return self._get("/v10/finance/quoteSummary/" + symbol,
                         params={"modules": "summaryDetail,defaultKeyStatistics,financialData"})

    def search_tickers(self, query: str) -> Dict[str, Any]:
        return self._get("/v1/finance/search",
                         params={"q": query, "quotesCount": 10, "newsCount": 0})

    def get_options(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                opts = ticker.option_chain(date) if date else ticker.option_chain()
                return {"success": True, "configured": True, "simulated": False,
                        "data": {
                            "calls": opts.calls.to_dict() if hasattr(opts, "calls") else {},
                            "puts": opts.puts.to_dict() if hasattr(opts, "puts") else {},
                        }, "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        return self._get(f"/v7/finance/options/{symbol}")

    def get_earnings(self, symbol: str) -> Dict[str, Any]:
        ticker = self._try_yfinance("Ticker", ticker=symbol)
        if ticker is not None:
            try:
                return {"success": True, "configured": True, "simulated": False,
                        "data": ticker.earnings.to_dict() if hasattr(ticker, "earnings") and hasattr(ticker.earnings, "to_dict") else {},
                        "error": None, "source": "yfinance"}
            except Exception as exc:
                logger.debug("Non-critical error: %s", exc)
        return self._get(f"/v10/finance/quoteSummary/{symbol}",
                         params={"modules": "earningsHistory,earningsTrend"})

    def get_news(self, symbol: str) -> Dict[str, Any]:
        return self._get("/v1/finance/search",
                         params={"q": symbol, "newsCount": 10, "quotesCount": 0})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        result = self.get_quote("AAPL")
        result["integration"] = self.INTEGRATION_NAME
        return result
