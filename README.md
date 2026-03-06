# Equity Research Agent System

Equity research for NSE/BSE listed Indian stocks using a LangGraph-based multi-agent system. Agents cover company overview, management, financial risk, concall evaluation (stubbed), and sectoral view; the pipeline runs to a single report. A CLI and a web UI (frontend + FastAPI backend) are provided.

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

To see each step of the graph (resolve → parallel research → aggregate → report) in [LangSmith](https://smith.langchain.com), add to your `.env`:

- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=ls__...` (create an API key in LangSmith settings)
- Optionally: `LANGSMITH_PROJECT=equity-research` (default project is `default`)

Then run the CLI as usual. Traces will appear in your LangSmith project with tags and metadata (symbol, exchange) so you can debug and inspect each node.

## Usage

Run research for a symbol (NSE):

```bash
python run.py --symbol RELIANCE --exchange NSE
```

The graph runs all research agents (company overview, management, financial risk, concall stub, sectoral), then generates the report and exits. The report is saved under the `reports/` directory as `<SYMBOL>_<timestamp>.pdf` or `.html` (e.g. `reports/RELIANCE_20250303_143022.pdf`).

### Running the UI

Run the backend and frontend in **two separate terminals**. The frontend proxies API requests to the backend.

**Terminal 1 – Backend** (from repo root; use the venv’s Python so the `nse` package is found):

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # if not already done
PYTHONPATH=. python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Using `python -m uvicorn` ensures the same interpreter (and venv) that has `nse` installed is used.

**Terminal 2 – Frontend**:

```bash
cd frontend
npm install   # first time only
npm run dev
```

Then open **http://localhost:5173**. Use the search bar to find a stock (NSE symbol or company name); select a suggestion to go to `/:symbol/report`. The report is generated in the background and shown when ready.

## Data sources

- **Company and market data**: Free NSE data via the `nse` package (company meta, quote, shareholding). Requests are rate-limited to avoid overloading NSE.
- **Financials**: Ratios (ROE, D/E, etc.) from `nifpy` (Yahoo Finance NSE tickers, e.g. RELIANCE.NS).
- **Latest data**: Research nodes use **OpenAI’s built-in web search** (Responses API with `web_search_preview`) so the model can fetch recent news and data when writing company overview, management, financial risk, and sectoral sections. No extra API key is required. If the Responses API is unavailable for your model, you can set `TAVILY_API_KEY` to use Tavily as a fallback.
- **Concall transcripts**: Not available from free NSE/BSE; the concall evaluator node is stubbed. You can plug in Trendlyne or another source later.

## Project structure

- `src/` – Core code: state schema, graph, config.
- `src/nodes/` – LangGraph nodes (resolve company, overview, management, financial risk, concall stub, sectoral, aggregate, report generator).
- `src/data/` – Data adapters (NSE client, financials, filings).
- `src/report/` – Jinja2 templates and CSS for the PDF report.
- `reports/` – Generated PDFs.
- `run.py` – CLI entrypoint.
- `backend/` – FastAPI app: symbol suggest (`NSE.lookup`), report job start/status/HTML.
- `frontend/` – Vite + React + TypeScript: landing search, report page with loader.

## Contributing / Node Development

When you implement or significantly change a node, update **`node-docs.txt`** at the project root before finishing. Each entry should cover:

- File locations (node, prompt, CSS, template)
- What the node does and how it works (data flow)
- Prompt design decisions (search strategy, output format instructions, HTML structure)
- CSS classes produced and their visual meaning
- Known limitations and future improvements
- Test results (which symbol, what date, what the output showed)

This file is maintained across sessions so future contributors (and AI assistants) can understand the system without re-reading the full code.

## License

Private / use as you see fit.
