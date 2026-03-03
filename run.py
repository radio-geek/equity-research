#!/usr/bin/env python3
"""CLI: run equity research for a symbol, then follow-up loop until user says 'I am Done'."""

import argparse
import uuid

from langgraph.types import Command

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

    while True:
        interrupt_payload = getattr(result, "__interrupt__", None) or (result if isinstance(result, dict) else {}).get("__interrupt__")
        if interrupt_payload is not None:
            prompt = interrupt_payload if isinstance(interrupt_payload, str) else "Your input:"
            try:
                user_input = input(f"\n{prompt}\n> ").strip()
            except EOFError:
                user_input = "I am Done"
            result = graph.invoke(Command(resume=user_input), config=config)
            continue

        values = result if isinstance(result, dict) else getattr(result, "values", result)
        if isinstance(values, dict) and values.get("report_path"):
            print(f"\nReport saved: {values['report_path']}")
            return
        print("\nSession ended.")
        return


if __name__ == "__main__":
    main()
