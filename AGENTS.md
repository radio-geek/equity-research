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

- **PostgreSQL** (required for auth and caching):
  - Create DB: `createdb equity_research` (or via psql)
  - Run migrations: `psql ... -f backend/migrations/001_init.sql` through `005_reports_requested_by_generation_ms.sql` (see README PostgreSQL section for full list)
  - Set `DATABASE_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL` in `.env`

- **Backend** (from repo root, with venv active):  
  `PYTHONPATH=. python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`  
  Use `python -m uvicorn` so the same interpreter (and `nse` package) is used.

- **Frontend**:
  `cd frontend && npm install && npm run dev`
  Dev server: `http://localhost:5173` (proxies API to backend).
  Styling uses **Tailwind v3** (`tailwindcss` + `autoprefixer` in `postcss.config.js`), not `@tailwindcss/postcss` v4, so dev/build does not depend on `@tailwindcss/oxide` native binaries or Node 20+.

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
| Backend API | `backend/main.py`, `backend/reports.py`, `backend/symbols.py`, `backend/cache.py`, `backend/pdf_render.py`, `backend/section_feedback_store.py`, `backend/job_store.py` |
| Rate limiting | `backend/main.py` — `slowapi` limiter with `@limiter.limit(...)` decorators; key: `user:{id}` (authenticated) or client IP (anonymous). Limits: reports 3/min+10/day, PDF 10/min, quote/indices 30/min, suggest 60/min, feedback 10/min, auth 10/min |
| Auth & sessions | `backend/auth.py` (Google OAuth2, JWT, DB-backed sessions), `backend/db.py` (psycopg2 pool) |
| DB migrations | `backend/migrations/*.sql` — run in order: `001_init.sql`, `002_sessions.sql`, `003_error_logs.sql`, `004_concall_transcripts.sql`, `005_reports_requested_by_generation_ms.sql` |
| Frontend auth | `frontend/src/contexts/AuthContext.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/components/ProtectedRoute.tsx` |
| Frontend | `frontend/src/` (Vite + React + TS) |
| Config / env | `src/config.py`, `.env` (from `.env.example`) |
| Vercel | `vercel.json` (build, output, rewrites), `api/index.py` (FastAPI serverless entrypoint) |
| GitHub Pages | `.github/workflows/deploy-pages.yml` (frontend only; backend on Render or elsewhere) |

---

## Vercel deployment

- **Frontend**: Built via `vercel.json` (`buildCommand`: `cd frontend && npm ci && npm run build`, `outputDirectory`: `frontend/dist`). SPA fallback rewrite serves `index.html` for non-API paths.
- **API**: `api/index.py` imports `backend.main:app` and wraps it in `VercelAuthPathMiddleware` so `/auth/*` requests (rewritten to `/api/vercel_auth/*`) are routed correctly. Root `requirements.txt` is used for the Python function.
- **CORS**: `backend/main.py` adds `VERCEL_URL` (https/http) to allowed origins when set.
- **Rate limiting**: `slowapi` uses in-memory storage; counters reset on every cold start and are not shared across Vercel function instances. Limits work correctly on Render (single persistent process).
- See [README.md](README.md) § Deploying on Vercel for env vars, Google OAuth production redirect URI, and serverless limitations (timeout, in-memory job store).

## GitHub Pages deployment (frontend only)

- **Frontend**: Deployed via `.github/workflows/deploy-pages.yml`. On push to `main`, the workflow builds the frontend (with `VITE_BASE_PATH` and `VITE_API_URL` from secret `RENDER_API_URL`), then deploys to GitHub Pages. Base path is `/<repo>/` (e.g. `/equity-research/`). `frontend/vite.config.ts` uses `VITE_BASE_PATH`; `frontend/src/main.tsx` uses `import.meta.env.BASE_URL` for React Router basename. Build script `build:pages` copies `index.html` to `404.html` for SPA deep links.
- **Backend**: Not deployed to Pages; must be hosted elsewhere (e.g. Render). Frontend on Pages calls the backend using the URL stored in the `RENDER_API_URL` repo secret (injected as `VITE_API_URL` at build time).
- **CORS**: Set `FRONTEND_URL` on the backend to the GitHub Pages origin (e.g. `https://<user>.github.io/equity-research`) so the backend allows requests from the frontend.
- See [README.md](README.md) § Deploying frontend to GitHub Pages.

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
- **Required (auth/DB)**: `DATABASE_URL` (PostgreSQL DSN), `JWT_SECRET` (32-char random string), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` (e.g. `http://localhost:8000/auth/google/callback`), `FRONTEND_URL` (e.g. `http://localhost:5173`).
- **Optional**: `TAVILY_API_KEY` (fallback search), `LANGSMITH_*` (tracing), `REPORTS_DIR`, `NSE_DOWNLOAD_FOLDER`.
- Never commit `.env` or real API keys. `.env.example` documents variables without values.

---

## Data and external services

- **NSE**: Free tier via `nse` package; rate-limited. Company meta, quote, shareholding.  
- **Financials**: `nifpy` (Yahoo Finance NSE tickers, e.g. RELIANCE.NS).  
- **LLM + search**: Research nodes use OpenAI Responses API with built-in web search; optional Tavily fallback if configured.  
- **Concall**: No free NSE/BSE transcripts; concall node uses web search and is documented in `node-docs.txt`.  
- **Caching**: Reports are cached in PostgreSQL (`reports` table, 24h TTL per symbol+exchange). Feedback stored in PostgreSQL (`feedback` table). The old `cache_data/` file-based cache is no longer used.
- **Auth**: Google OAuth2 flow via `backend/auth.py`. Sessions stored in PostgreSQL (`sessions` table). JWT embeds `jti = session UUID`; logout revokes the DB row. Run migrations before starting the backend: `psql -U postgres -d equity_research -f backend/migrations/001_init.sql` and `002_sessions.sql`.

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
- Backend CORS is set for local dev origins (localhost:5173–5175, 127.0.0.1); `FRONTEND_URL` env var is included automatically.  
- Cache and feedback paths are local and gitignored; do not expose them publicly without access control.  
- NSE and third-party APIs: respect rate limits; do not log full responses if they contain PII.

---

## Quick reference for agents

1. **Adding a new research node**: Implement in `src/nodes/<name>.py`, add prompt in `src/nodes/prompts.py`, register in `src/graph.py` (fan-out and edge to aggregate), add state fields in `src/state.py`, wire section in `src/report/templates/base.html` and styles in `src/report/styles.css`, then **update `node-docs.txt`**.  
2. **Changing a prompt**: Edit `src/nodes/prompts.py`; if output structure or CSS classes change, update report template/CSS and `node-docs.txt`.  
3. **Backend API**: Routes in `backend/main.py`; report job logic in `backend/reports.py`; cache in `backend/cache.py`; PDF in `backend/pdf_render.py`. When adding a new route, add a `@limiter.limit("N/period")` decorator and ensure `request: Request` is in the function signature (required by `slowapi`).
4. **Report layout/styling**: `src/report/templates/base.html`, `src/report/styles.css`, `src/nodes/report_generator.py` (payload assembly).  
5. **State contract**: Any new state key used by nodes should be added to `ResearchState` in `src/state.py` and documented in `node-docs.txt` if it affects report or node behavior.

Keeping this file and `node-docs.txt` accurate will make future agent and human contributions smoother.
