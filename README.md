# Equity Research Agent System

Equity research for NSE/BSE listed Indian stocks using a LangGraph-based multi-agent system. Agents cover company overview, management, financial risk, concall evaluation (stubbed), and sectoral view; the pipeline runs to a single report. A CLI and a web UI (frontend + FastAPI backend) are provided.

## Prerequisites

- Python 3.10+
- pip
- PostgreSQL 14+ (local install or hosted)
- Node.js 18+ (for the frontend)

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

4. Copy the example env file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   - `OPENAI_API_KEY` – your OpenAI API key
   - `OPENAI_MODEL` – e.g. `gpt-4o`
   - `TAVILY_API_KEY` – (optional) fallback for web search; get one at [tavily.com](https://tavily.com)
   - `DATABASE_URL` – see PostgreSQL setup below
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` – see Google Auth setup below
   - `JWT_SECRET` – generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`

## PostgreSQL Setup

The backend uses PostgreSQL for report caching, user accounts, and feedback.

### 1. Create the database

```bash
# macOS (Homebrew)
psql -U postgres -c "CREATE DATABASE equity_research;"

# macOS (PostgreSQL.app / installer)
/Library/PostgreSQL/18/bin/psql -U postgres -c "CREATE DATABASE equity_research;"
```

### 2. Run the migration

```bash
psql -U postgres -d equity_research -f backend/migrations/001_init.sql

# or with full path on macOS installer
/Library/PostgreSQL/18/bin/psql -U postgres -d equity_research -f backend/migrations/001_init.sql
```

This creates three tables: `users`, `reports` (cached report payloads, 24h TTL), `feedback`.

### 3. Set DATABASE_URL in .env

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/equity_research
```

Replace `YOUR_PASSWORD` with the password you set during PostgreSQL installation.

## Google OAuth Setup

Used for user login. Reports and feedback can be submitted without login; auth is optional but required to associate feedback with a user.

### 1. Create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Add Authorized redirect URI: `http://localhost:8000/auth/google/callback`
5. Copy the **Client ID** and **Client Secret**

### 2. Set in .env

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
JWT_SECRET=<32-byte hex string from python3 -c "import secrets; print(secrets.token_hex(32))">
```

### Auth flow

1. User clicks **Sign in with Google** on the landing page
2. Browser goes to `GET /auth/google` → redirected to Google consent
3. Google redirects to `GET /auth/google/callback?code=...`
4. Backend exchanges code for user info, upserts user in `users` table, issues a JWT
5. Frontend stores JWT in `localStorage`; subsequent requests include `Authorization: Bearer <token>`
6. `GET /auth/me` returns the logged-in user’s profile

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

- **Caching**: Reports are cached in the `reports` PostgreSQL table for 24 hours per symbol. If a cached report exists, it is served immediately without re-running the pipeline.
- **PDF download**: On the report page, use “Download PDF” to get a styled PDF (WeasyPrint when system libs are available; otherwise ReportLab fallback). On macOS, install Pango/Cairo for WeasyPrint: `brew install pango cairo`.
- **Feedback**: Thumbs up/down and an optional comment can be submitted; stored in the `feedback` PostgreSQL table. If logged in, feedback is linked to the user.
- **Auth**: “Sign in with Google” button on the landing page. JWT stored in `localStorage`. Requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `JWT_SECRET` in `.env`.

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
- `backend/` – FastAPI app: symbol suggest, report job start/status, PDF export, feedback, Google OAuth + JWT auth.
  - `backend/db.py` – PostgreSQL connection pool and query helpers
  - `backend/auth.py` – Google OAuth2 flow, JWT create/verify, `get_current_user` dependency
  - `backend/cache.py` – Report cache backed by `reports` table (24h TTL)
  - `backend/feedback_store.py` – Feedback stored in `feedback` table
  - `backend/migrations/001_init.sql` – Initial schema (users, reports, feedback)
- `frontend/` – Vite + React + TypeScript: landing (search, indices ticker, review carousel), report page with PDF download and feedback (thumbs up/down + comment).

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
