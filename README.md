# Equity Research Agent System

Equity research for NSE/BSE listed Indian stocks using a LangGraph-based multi-agent system. Agents cover company overview, management, financial risk, concall evaluation (stubbed), and sectoral view; you can ask follow-up questions and generate a PDF report when done.

## Prerequisites

- Python 3.10 or 3.11
- pip

## Setup

1. Clone the repo and go to the project directory:
   ```bash
   cd equity-research
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the example env file and set your OpenAI key and model:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   - `OPENAI_API_KEY` – your OpenAI API key
   - `OPENAI_MODEL` – e.g. `gpt-4o` or `gpt-5.2` when available
   - `TAVILY_API_KEY` – (optional) fallback for web search if OpenAI’s built-in search is unavailable; get one at [tavily.com](https://tavily.com).

### Visualizing runs with LangSmith

To see each step of the graph (resolve → parallel research → aggregate → follow-up → report) in [LangSmith](https://smith.langchain.com), add to your `.env`:

- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=ls__...` (create an API key in LangSmith settings)
- Optionally: `LANGSMITH_PROJECT=equity-research` (default project is `default`)

Then run the CLI as usual. Traces will appear in your LangSmith project with tags and metadata (symbol, exchange) so you can debug and inspect each node.

## Usage

Run research for a symbol (NSE):

```bash
python run.py --symbol RELIANCE --exchange NSE
```

The graph runs all research agents (company overview, management, financial risk, concall stub, sectoral), then prints a prompt. Type a question about the research and press Enter to get an answer, or type **I am Done** (case-insensitive) to generate the PDF report and exit.

The PDF is saved under the `reports/` directory as `<SYMBOL>_<timestamp>.pdf` (e.g. `reports/RELIANCE_20250303_143022.pdf`).

## Data sources

- **Company and market data**: Free NSE data via the `nse` package (company meta, quote, shareholding). Requests are rate-limited to avoid overloading NSE.
- **Financials**: Ratios (ROE, D/E, etc.) from `nifpy` (Yahoo Finance NSE tickers, e.g. RELIANCE.NS).
- **Latest data**: Research nodes use **OpenAI’s built-in web search** (Responses API with `web_search_preview`) so the model can fetch recent news and data when writing company overview, management, financial risk, and sectoral sections. No extra API key is required. If the Responses API is unavailable for your model, you can set `TAVILY_API_KEY` to use Tavily as a fallback.
- **Concall transcripts**: Not available from free NSE/BSE; the concall evaluator node is stubbed. You can plug in Trendlyne or another source later.

## Project structure

- `src/` – Core code: state schema, graph, config.
- `src/nodes/` – LangGraph nodes (resolve company, overview, management, financial risk, concall stub, sectoral, aggregate, follow-up, report generator).
- `src/data/` – Data adapters (NSE client, financials, filings).
- `src/report/` – Jinja2 templates and CSS for the PDF report.
- `reports/` – Generated PDFs.
- `run.py` – CLI entrypoint.

## License

Private / use as you see fit.
