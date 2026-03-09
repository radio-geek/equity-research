"""Resolve company: fetch NSE meta, quote, shareholding, financial ratios and set state."""

from __future__ import annotations

import logging
from typing import Any

from src.config import get_nse_download_folder
from src.data import financials, nse_client
from src.state import ResearchState

logger = logging.getLogger(__name__)


def resolve_company(state: ResearchState) -> dict[str, Any]:
    """Fetch company metadata and key data from NSE; populate state for downstream nodes."""
    symbol = (state.get("symbol") or "").strip().upper()
    exchange = (state.get("exchange") or "NSE").strip().upper()
    if not symbol:
        logger.warning("resolve_company: no symbol in state")
        return {"company_name": "", "sector": "", "meta": {}, "quote": {}, "shareholding": [], "financial_ratios": []}

    logger.info("resolve_company: starting for %s (%s)", symbol, exchange)
    folder = get_nse_download_folder()
    meta = {}
    quote = {}
    shareholding: list = []
    financial_ratios: list = []

    try:
        meta = nse_client.get_meta(symbol, folder)
        logger.info("resolve_company: meta %s", "ok" if meta else "empty")
    except Exception as e:
        logger.warning("NSE meta failed for %s: %s", symbol, e)

    try:
        quote = nse_client.get_quote(symbol, folder)
        logger.info("resolve_company: quote %s", "ok" if quote else "empty")
    except Exception as e:
        logger.warning("NSE quote failed for %s: %s", symbol, e)

    try:
        shareholding = nse_client.get_shareholding(symbol, folder)
        logger.info("resolve_company: shareholding %s", "ok (%d items)" % len(shareholding) if shareholding else "empty")
    except Exception as e:
        logger.warning("NSE shareholding failed for %s: %s", symbol, e)

    try:
        financial_ratios = financials.get_financial_ratios(symbol, exchange)
        logger.info("resolve_company: financial_ratios %s", "ok (%d)" % len(financial_ratios) if financial_ratios else "empty")
    except Exception as e:
        logger.warning("Financial ratios failed for %s: %s", symbol, e)

    company_name = symbol
    sector = ""
    if meta:
        if isinstance(meta.get("symbolInfo"), list) and meta["symbolInfo"]:
            info = meta["symbolInfo"][0]
            company_name = info.get("companyName") or company_name
            sector = info.get("industry") or info.get("sector") or ""
        else:
            company_name = meta.get("companyName") or company_name
            sector = meta.get("industry") or meta.get("sector") or ""

    logger.info("resolve_company: done for %s -> company_name=%s, sector=%s", symbol, company_name, sector or "(none)")
    return {
        "company_name": company_name,
        "sector": sector,
        "industry": sector,
        "meta": meta,
        "quote": quote,
        "shareholding": shareholding,
        "financial_ratios": financial_ratios,
    }
