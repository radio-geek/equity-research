#!/usr/bin/env python3
"""CLI: run equity research for a symbol; single invoke produces report."""

import argparse
import uuid

from src.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Equity research for NSE/BSE stocks")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE)")
    parser.add_argument("--exchange", default="NSE", help="Exchange (default: NSE)")
    args = parser.parse_args()

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
    result = graph.invoke(initial_state, config=config)

    values = result if isinstance(result, dict) else getattr(result, "values", result)
    if isinstance(values, dict) and values.get("report_payload"):
        meta = (values["report_payload"] or {}).get("meta", {})
        print(f"\nReport ready for {meta.get('company_name', symbol)} ({meta.get('symbol', symbol)}).")
    else:
        print("\nSession ended.")


if __name__ == "__main__":
    main()
