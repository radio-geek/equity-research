#!/usr/bin/env python3
"""CLI: run equity research for a symbol; single invoke produces report."""

import argparse
import logging
import sys
import traceback
import uuid

from src.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Equity research for NSE/BSE stocks")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE)")
    parser.add_argument("--exchange", default="NSE", help="Exchange (default: NSE)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    logger = logging.getLogger(__name__)

    symbol = args.symbol.strip().upper()
    exchange = args.exchange.strip().upper()
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["equity-research", symbol, exchange],
        "metadata": {"symbol": symbol, "exchange": exchange},
        "run_name": f"equity-research-{symbol}-{exchange}",
    }

    graph = build_graph()
    initial_state = {"symbol": symbol, "exchange": exchange, "messages": []}

    print(f"Running research for {symbol} ({exchange})...")
    logger.info("Starting graph invoke for %s (%s)", symbol, exchange)
    try:
        result = graph.invoke(initial_state, config=config)
    except Exception as e:
        logger.exception("Graph invoke failed: %s", e)
        print(f"\nError: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    values = result if isinstance(result, dict) else getattr(result, "values", result)
    if isinstance(values, dict) and values.get("report_payload"):
        meta = (values["report_payload"] or {}).get("meta", {})
        logger.info("Report generated successfully for %s", symbol)
        print(f"\nReport ready for {meta.get('company_name', symbol)} ({meta.get('symbol', symbol)}).")
    else:
        logger.warning("No report_payload in result; keys: %s", list(values.keys()) if isinstance(values, dict) else "n/a")
        print("\nSession ended.")


if __name__ == "__main__":
    main()
