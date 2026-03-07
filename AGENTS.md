# AGENTS.md

This file is the **README for AI coding agents** working on the Equity Research project. It provides setup, conventions, and instructions so agents can develop and modify the codebase effectively. For human-oriented overview and contribution guidelines, see [README.md](README.md).

---

## Project overview

- **What it is**: A LangGraph-based multi-agent system for equity research on NSE/BSE listed Indian stocks. The pipeline runs: **resolve company** → **parallel research nodes** (overview, management, financial risk, auditor flags, concall evaluation, sectoral, qoq financials) → **aggregate** → **report generator** → PDF/HTML output.
- **Stack**: Python 3.10/3.11 (LangGraph, LangChain OpenAI, Pydantic), FastAPI backend, Vite + React + TypeScript frontend. Data: free NSE (`nse`), financials (`nifpy`/yfinance), LLM web search (OpenAI Responses API or optional Tavily).
- **Outputs**: Reports under `reports/` (CLI) or served/cached via backend; frontend at `http://localhost:5173` with report page, PDF download, and feedback.

---

## Setup commands

- **Python (required)**  
  - Create venv: `python3 -m venv .venv`  
  - Activate: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)  
  - Install deps: `pip install -r requirements.txt`  
  - Copy env: `cp .env.example .env` and set `OPENAI_API_KEY`, `OPENAI_MODEL` (e.g. `gpt-4o`). Optional: `TAVILY_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

- **Backend** (from repo root, with venv active):  
  `PYTHONPATH=. python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`  
  Use `python -m uvicorn` so the same interpreter (and `nse` package) is used.

- **Frontend**:  
  `cd frontend && npm install && npm run dev`  
  Dev server: `http://localhost:5173` (proxies API to backend).

- **CLI (research only)**:  
  `python run.py --symbol RELIANCE --exchange NSE`  
  Report is written to `reports/<SYMBOL>_<timestamp>.pdf` or `.html`.

---

## Key paths (where to edit)

| Area | Location |
|------|----------|
| Graph definition | `src/graph.py` |
| Shared state schema | `src/state.py` |
| Research nodes | `src/nodes/*.py` (resolve_company, company_overview, management, financial_risk, auditor_flags, concall_evaluator, sectoral, qoq_financials, aggregate, report_generator) |
| All node prompts | `src/nodes/prompts.py` |
| NSE / financials / filings | `src/data/*.py` |
| Report HTML/CSS | `src/report/templates/`, `src/report/styles.css`, `src/report/charts.py` |
| Backend API | `backend/main.py`, `backend/reports.py`, `backend/symbols.py`, `backend/cache.py`, `backend/pdf_render.py`, `backend/feedback_store.py`, `backend/job_store.py` |
| Frontend | `frontend/src/` (Vite + React + TS) |
| Config / env | `src/config.py`, `.env` (from `.env.example`) |

---

## Node development (mandatory)

When you **implement or significantly change a research or report node**, you **must** update **`node-docs.txt`** at the project root before finishing. Each entry should cover:

- **File locations**: node module, prompt function, CSS, report template section.
- **What the node does** and **data flow** (inputs from state, outputs written to state).
- **Prompt design**: search strategy, output format (e.g. HTML with exact class names), token/section ordering if relevant.
- **CSS classes** produced and their meaning (for report styling).
- **Known limitations** and future improvements.
- **Test results**: symbol used, date, and a short note on output (so future agents don’t re-guess behavior).

This file is the single source of truth for node behavior across sessions; keep it accurate and concise.

---

## Code style and practices

- **Python**  
  - Use type hints; state and API payloads use Pydantic or TypedDict where appropriate.  
  - Prefer small, focused functions; avoid silent failure—check and handle errors.  
  - Follow existing patterns in `src/nodes/` and `src/data/` (e.g. state in/out, prompt helpers in `prompts.py`).  
  - No hardcoded secrets; use `os.getenv` / `python-dotenv` and `.env`.

- **Frontend**  
  - TypeScript; follow existing structure under `frontend/src/`.  
  - Run `npm run lint` and `npm run build` before committing.

- **Conventions**  
  - Workspace rules in `.cursor/rules/` (e.g. Go testing/development) apply where relevant; this repo is primarily Python + TypeScript.  
  - Prefer composition and clear boundaries between graph nodes, data layer, and report rendering.

---

## Testing instructions

- **Backend / graph**: There is no pytest layout yet. When adding or changing Python behavior, prefer adding tests (e.g. under `tests/` or beside modules) with table-driven or parametrized cases where applicable. Mock external I/O (NSE, OpenAI, Tavily).  
- **Frontend**: Run `npm run build` and `npm run lint` from `frontend/`. Fix any type or lint errors before finishing.  
- **Manual smoke test**: After graph or node changes, run CLI for one symbol, e.g. `python run.py --symbol RELIANCE --exchange NSE`, and confirm a report is generated and key sections appear. For UI changes, run backend + frontend and verify report page and PDF download.

---

## Environment and secrets

- **Required**: `OPENAI_API_KEY`, `OPENAI_MODEL` in `.env`.  
- **Optional**: `TAVILY_API_KEY` (fallback search), `LANGSMITH_*` (tracing), `REPORTS_DIR`, `NSE_DOWNLOAD_FOLDER`.  
- Never commit `.env` or real API keys. `.env.example` documents variables without values.

---

## Data and external services

- **NSE**: Free tier via `nse` package; rate-limited. Company meta, quote, shareholding.  
- **Financials**: `nifpy` (Yahoo Finance NSE tickers, e.g. RELIANCE.NS).  
- **LLM + search**: Research nodes use OpenAI Responses API with built-in web search; optional Tavily fallback if configured.  
- **Concall**: No free NSE/BSE transcripts; concall node uses web search and is documented in `node-docs.txt`.  
- **Caching**: Backend caches reports under `cache_data/reports/` (e.g. 24h per symbol); feedback in `cache_data/feedback.json`. Both are gitignored.

---

## Build and run summary

| Task | Command |
|------|--------|
| Install Python deps | `pip install -r requirements.txt` (with venv active) |
| Run CLI research | `python run.py --symbol <SYMBOL> --exchange NSE` |
| Start backend | `PYTHONPATH=. python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000` |
| Install frontend deps | `cd frontend && npm install` |
| Frontend dev | `cd frontend && npm run dev` |
| Frontend build | `cd frontend && npm run build` |
| Frontend lint | `cd frontend && npm run lint` |

---

## PR / commit guidelines

- **Before committing**: Run frontend `npm run lint` and `npm run build`; fix errors.  
- **After node changes**: Update `node-docs.txt` as described above.  
- **Title/scope**: Use clear, scoped messages (e.g. `[node] Add X`, `[backend] Fix Y`, `[frontend] Z`).  
- **No secrets**: Ensure no `.env` or API keys are staged.

---

## Security considerations

- All secrets in environment variables only; no keys in repo.  
- Backend CORS is set for local dev origins (e.g. localhost:5173, 127.0.0.1).  
- Cache and feedback paths are local and gitignored; do not expose them publicly without access control.  
- NSE and third-party APIs: respect rate limits; do not log full responses if they contain PII.

---

## Quick reference for agents

1. **Adding a new research node**: Implement in `src/nodes/<name>.py`, add prompt in `src/nodes/prompts.py`, register in `src/graph.py` (fan-out and edge to aggregate), add state fields in `src/state.py`, wire section in `src/report/templates/base.html` and styles in `src/report/styles.css`, then **update `node-docs.txt`**.  
2. **Changing a prompt**: Edit `src/nodes/prompts.py`; if output structure or CSS classes change, update report template/CSS and `node-docs.txt`.  
3. **Backend API**: Routes in `backend/main.py`; report job logic in `backend/reports.py`; cache in `backend/cache.py`; PDF in `backend/pdf_render.py`.  
4. **Report layout/styling**: `src/report/templates/base.html`, `src/report/styles.css`, `src/nodes/report_generator.py` (payload assembly).  
5. **State contract**: Any new state key used by nodes should be added to `ResearchState` in `src/state.py` and documented in `node-docs.txt` if it affects report or node behavior.

Keeping this file and `node-docs.txt` accurate will make future agent and human contributions smoother.
