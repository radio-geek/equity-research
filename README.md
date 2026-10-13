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

The backend uses PostgreSQL for report caching, user accounts, sessions, and feedback.

### 1. Install PostgreSQL

- **macOS (Homebrew)**: `brew install postgresql@16 && brew services start postgresql@16`
- **macOS (installer)**: Download from [postgresql.org](https://www.postgresql.org/download/macosx/) — installs to `/Library/PostgreSQL/<version>/bin/`
- **Linux**: `sudo apt install postgresql` or equivalent

### 2. Create the database

```bash
# Homebrew / Linux
psql -U postgres -c "CREATE DATABASE equity_research;"

# macOS installer (adjust version number as needed)
/Library/PostgreSQL/18/bin/psql -U postgres -c "CREATE DATABASE equity_research;"
```

### 3. Run all migrations

```bash
# Users, reports, and feedback tables
psql -U postgres -d equity_research -f backend/migrations/001_init.sql

# Sessions table (required for Google Auth)
psql -U postgres -d equity_research -f backend/migrations/002_sessions.sql

# Error logs table
psql -U postgres -d equity_research -f backend/migrations/003_error_logs.sql

# Concall transcript cache table
psql -U postgres -d equity_research -f backend/migrations/004_concall_transcripts.sql

# Report cache columns (requested_by, generation_ms) — required for set_cached_report()
psql -U postgres -d equity_research -f backend/migrations/005_reports_requested_by_generation_ms.sql

# Earnings date calendar (board-meeting intimation log + derived calendar)
psql -U postgres -d equity_research -f backend/migrations/008_earnings_dates.sql
```

Or run every migration in order with `python backend/run_migrations.py` (uses `DATABASE_URL`;
all migrations are idempotent, so re-running is safe).

If using the macOS installer, prefix with the full path e.g. `/Library/PostgreSQL/18/bin/psql`.
If prompted for a password, prefix each command with `PGPASSWORD=your_password`.

> **Note for `equity_app` users:** `ALTER DEFAULT PRIVILEGES` only covers tables created *after* the command is run. For each new migration table you must also grant access manually. After running migration 004, run this as `postgres`:
> ```sql
> GRANT SELECT, INSERT, UPDATE, DELETE ON concall_transcripts TO equity_app;
> GRANT USAGE, SELECT ON SEQUENCE concall_transcripts_id_seq TO equity_app;
> ```

### 4. Create a least-privilege app user (required)

The backend connects as a dedicated `equity_app` user instead of the `postgres` superuser. This limits blast radius if the app is ever compromised — `equity_app` can only read/write data rows, not drop tables or access other databases.

Run this once as the `postgres` superuser:

```bash
psql -U postgres -d equity_research
```

Then paste:

```sql
CREATE USER equity_app WITH PASSWORD 'choose-a-strong-password';
GRANT CONNECT ON DATABASE equity_research TO equity_app;
GRANT USAGE ON SCHEMA public TO equity_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO equity_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO equity_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO equity_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO equity_app;
```

Replace `choose-a-strong-password` with a strong random string — you can generate one with:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 5. Add DATABASE_URL to .env

```
DATABASE_URL=postgresql://equity_app:your-chosen-password@localhost:5432/equity_research
```

Use the `equity_app` user and the password you set above — **not** the `postgres` superuser.

## Google OAuth Setup

Used for user login. Reports can be generated without login; auth is optional but required to associate feedback with a user account.

### 1. Create a Google Cloud project and OAuth client

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or select an existing one)
3. Go to **APIs & Services** → **OAuth consent screen**
   - User type: **External**
   - Fill in app name, support email, developer email
   - Scopes: add `email`, `profile`, `openid`
   - Test users: add the Google accounts you want to use during development
4. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: add `http://localhost:8000/auth/google/callback`
5. Copy the **Client ID** and **Client Secret**

### 2. Add to .env

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
JWT_SECRET=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
```

> **Important:** `FRONTEND_URL` must match the exact URL your frontend is running on (including port). If Vite starts on `5174` or `5175` instead of `5173`, update this value.

### 3. Create frontend/.env

The frontend needs to know where the backend is. Create `frontend/.env` (this file is gitignored):

```
VITE_API_URL=http://localhost:8000
```

### Auth flow

1. User clicks **Sign in with Google** → browser navigates to `GET /auth/google`
2. Backend sets a CSRF cookie and redirects to Google’s consent screen
3. After consent, Google redirects to `GET /auth/google/callback?code=...&state=...`
4. Backend verifies CSRF state, exchanges code for user info, upserts user in `users` table, creates a DB-backed session, and issues a JWT
5. Browser is redirected to `FRONTEND_URL/?token=<jwt>`
6. Frontend stores JWT in `localStorage`; all API requests include `Authorization: Bearer <token>`
7. `GET /auth/me` returns the logged-in user’s profile

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| Blank page after clicking "Sign in with Google" | `frontend/.env` missing — `VITE_API_URL` not set |
| Redirected to `/?auth_error=csrf_failed` | CSRF state cookie not sent — try clearing browser cookies and retrying |
| Redirected to `/?auth_error=server_error` | Check backend logs; usually a DB connection error or missing env vars |
| Still shows "Sign in with Google" after login | `FRONTEND_URL` mismatch — frontend port doesn’t match the value in `.env` |
| "redirect_uri_mismatch" on Google’s page | The redirect URI in Google Cloud Console doesn’t match `GOOGLE_REDIRECT_URI` in `.env` |
| "Access blocked: app not verified" | Add your Google account as a test user in the OAuth consent screen |

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

- **Caching**: Reports are cached in the `reports` PostgreSQL table for 24 hours per symbol (concall companies) or 7 days (no-concall companies). If a cached report exists, it is served immediately without re-running the pipeline.
- **PDF download**: On the report page, use “Download PDF” to get a styled PDF (1) Playwright headless Chromium—run `playwright install chromium` after pip install; (2) WeasyPrint—e.g. `brew install pango cairo` on macOS; (3) ReportLab fallback. For deployment, install Chromium for best PDF fidelity.
- **Feedback**: Per-section star ratings and suggestions stored in `section_feedback` table. If logged in, feedback is linked to the user.
- **Auth**: “Sign in with Google” button on the landing page. JWT stored in `localStorage`. Requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `JWT_SECRET` in `.env`.
- **Rate limiting**: Enforced via `slowapi` on all public endpoints. Authenticated users are limited by user ID; anonymous by IP. Key limits: report generation (`POST /api/reports`) is capped at **3/minute and 10/day** per user to control LLM costs. Other endpoints: PDF download 10/min, live quote 30/min, symbol suggest 60/min. Exceeding a limit returns `429 Too Many Requests`.

## Deploying on Vercel

The project is set up for [Vercel](https://vercel.com): the frontend is built from `frontend/` and the FastAPI backend runs as a serverless function via `api/index.py`. Static assets and API/auth routes are served from the same deployment.

### 1. Connect your repo

1. Go to [vercel.com](https://vercel.com) and import your Git repository.
2. Use the **root** of the repo (no root directory override).
3. Vercel will use `vercel.json`: it builds the frontend (`buildCommand`: `cd frontend && npm ci && npm run build`), sets `outputDirectory` to `frontend/dist`, and routes `/api/*` and `/auth/*` to the Python function.

### 2. Environment variables

In the Vercel project **Settings → Environment Variables**, add the same variables you use locally (see [Setup](#setup) and [Google OAuth Setup](#google-oauth-setup)):

- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `DATABASE_URL` (use a hosted PostgreSQL, e.g. [Neon](https://neon.tech), [Supabase](https://supabase.com), or [Railway](https://railway.app))
- `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `FRONTEND_URL` = your Vercel deployment URL (e.g. `https://your-project.vercel.app`)

Optional: `TAVILY_API_KEY`, `LANGSMITH_*`. `VERCEL_URL` is set automatically by Vercel; the backend adds it to CORS for preview/production.

### 3. Google OAuth for production

In [Google Cloud Console](https://console.cloud.google.com) → **Credentials** → your OAuth client:

- Add an **Authorized redirect URI**: `https://<your-vercel-domain>/auth/google/callback`
- Set `GOOGLE_REDIRECT_URI` in Vercel to that same URL (e.g. `https://your-project.vercel.app/auth/google/callback`).

### 4. Database and migrations

Run the same PostgreSQL migrations on your hosted database as in [PostgreSQL Setup](#postgresql-setup) (`001_init.sql`, `002_sessions.sql`) before deploying.

### 5. Limitations on Vercel

- **Function timeout**: Report generation runs inside the serverless function. Long runs may hit the plan limit (e.g. 60s on Hobby). Cached reports are returned immediately without re-running the pipeline.
- **In-memory job store**: The backend uses an in-memory job store; on serverless, background report jobs may not complete after the HTTP response is sent. For production at scale, consider a queue (e.g. Vercel background functions or an external worker) and a persistent job store.
- **Rate limiting**: `slowapi` uses in-memory storage; counters reset on every cold start. Limits are enforced per function instance, not globally across Vercel invocations.

## Deploying frontend to GitHub Pages

You can deploy **only the frontend** (static SPA) to [GitHub Pages](https://pages.github.com/) using the included GitHub Actions workflow. The backend does **not** run on GitHub Pages; it must be hosted elsewhere (e.g. [Render](https://render.com)).

### 1. Backend

Host the FastAPI backend on Render or another platform (see Render or your host’s docs for deploy steps). Set `FRONTEND_URL` on the backend to your GitHub Pages URL (e.g. `https://<user>.github.io/equity-research`).

**PDF on Render:** Render’s runtime instance often **does not include** browser files produced during the build (for example paths listed in `.gitignore` can be omitted from the deploy slug, leaving an empty `PLAYWRIGHT_BROWSERS_PATH`). Use this setup:

1. **Build Command:** `bash scripts/render_build.sh` (same as before: `pip install`, then `python -m playwright install` into `./playwright-browsers`; the script fails the build if Chromium is missing).
2. **Start Command:** `bash scripts/render_start.sh` — before Uvicorn, runs `python -m playwright install chromium` on the **runtime** disk so the executable always exists (first boot may take ~30–60s; later boots are fast if the layer is cached).
3. In the Render dashboard, **remove** `PLAYWRIGHT_BROWSERS_PATH` unless you know you need it — a stale value pointing at an empty folder breaks PDFs.

`playwright-browsers/` is not gitignored so it can ship in the slug if your host includes it; `render_start.sh` still fixes the common case when it does not. For missing system libraries at launch, use a Dockerfile-based service or a Playwright base image.

### 2. Repository secret

In your GitHub repo: **Settings → Secrets and variables → Actions** → **New repository secret**:

- **Name**: `RENDER_API_URL`
- **Value**: Your backend URL (e.g. `https://equity-research-api.onrender.com`) with no trailing slash.

The workflow injects this as `VITE_API_URL` at build time so the frontend calls your backend.

### 3. Enable GitHub Pages

In the repo: **Settings → Pages** → **Source**: choose **GitHub Actions**.

### 4. Deploy

Push to the `main` branch. The workflow (`.github/workflows/deploy-pages.yml`) builds the frontend with the correct base path and deploys to Pages. The site will be at `https://<user>.github.io/<repo>/` (e.g. `https://<user>.github.io/equity-research/`).

### 5. CORS

On the backend (e.g. Render), set `FRONTEND_URL` to your Pages origin, e.g. `https://<user>.github.io` or `https://<user>.github.io/equity-research`, so the backend allows requests from the frontend.

## Results Calendar

A screener at `/results-calendar` (public, no sign-in) listing companies that have announced a
quarterly-results date, with how that timing compares to the same period last year and to the
previous period.

**Why "lag" and not dates.** Q1 results land in July and Q2 in October, so comparing "17 Jul" to
"17 Oct" is meaningless. Every comparison uses **lag — days from period end to declaration** — and
each delta is simply `lag_current − lag_peer`. A negative delta means the company reported earlier.

| Column | Meaning |
|---|---|
| Period | e.g. `Q2 FY27`; badged when the filer is half-yearly or annual |
| Results date | The announced date, plus how far away it is. Marked when revised |
| Lag | Days from period end to declaration |
| vs last year (YoY) | Same period one year earlier, in days |
| vs prev period (QoQ) | Previous period, in days. Refused across a Q4/annual boundary |
| Announced | When the intimation was filed, and how many days of notice |

**Data source.** NSE `/api/corporate-board-meetings` via the `nse` package, which serves
forthcoming *and* historical windows, market-wide. BSE's announcement API returns 403 (Akamai) and
Screener carries no announcement dates, so neither is a fallback.

**Populating it.** Set up as a Render Cron Job (daily during results season) running:

```bash
python scripts/refresh_earnings_calendar.py            # last 7 days through 30 days ahead
python scripts/refresh_earnings_calendar.py --backfill-months 17 --stats   # seed history
python scripts/refresh_earnings_calendar.py --backfill-months 17 --reattribute
```

Needs `DATABASE_URL` only. All writes are idempotent upserts, so overlapping windows are safe.
`--stats` prints the attribution-quality breakdown; investigate if the `proximity` share grows.

`--reattribute` rebuilds the calendar from the stored intimation log **without re-fetching NSE**.
That is what the raw `board_meeting_intimations` table is for: period attribution is heuristic and
will be improved over time, and a parser fix must roll out over all history in seconds.

**Caveats worth knowing.**

- Dates are board-meeting *intimations* — the company's stated plan, which can move. Postponements
  are preserved (`first_intimated_date`, `revision_count`), not overwritten.
- Period attribution is inferred, mostly from the filing text and otherwise from the meeting date.
  Rows attributed with low confidence are badged "inferred" in the UI.
- Backfill at least **17 months**: a 12-month window clips the prior-year peer for the earliest
  quarter, leaving those rows with no YoY comparison.
- The summary strip skews "earlier" mid-season, because only companies that have already announced
  appear and they are the early reporters by definition. Per-company deltas are sound; the
  aggregate ratio is not.
- The signal is genuinely weak. Reporting early correlates with good news in the literature, but
  noisily — timing also moves for auditor scheduling and board availability. The UI deliberately
  shows neutral numbers rather than a verdict.

## Data sources

- **Company and market data**: Free NSE data via the `nse` package (company meta, quote, shareholding). Requests are rate-limited to avoid overloading NSE.
- **Financials**: Ratios (ROE, D/E, etc.) from `nifpy` (Yahoo Finance NSE tickers, e.g. RELIANCE.NS).
- **Latest data**: Research nodes use **OpenAI’s built-in web search** (Responses API with `web_search_preview`) so the model can fetch recent news and data when writing company overview, management, financial risk, and sectoral sections. No extra API key is required. If the Responses API is unavailable for your model, you can set `TAVILY_API_KEY` to use Tavily as a fallback.
- **Concall transcripts**: Not available from free NSE/BSE; the concall evaluator node is stubbed. You can plug in Trendlyne or another source later.
- **Results dates**: NSE board-meeting intimations (`/api/corporate-board-meetings`) via the `nse` package — market-wide, and queryable over historical windows. Note that NSE's `/api/search/autocomplete` is blocked by bot protection while this endpoint is not, so do not assume all NSE endpoints behave the same. See § Results Calendar.

## Project structure

- `src/` – Core code: state schema, graph, config.
- `src/nodes/` – LangGraph nodes (resolve company, overview, management, financial risk, concall stub, sectoral, aggregate, report generator).
- `src/data/` – Data adapters (NSE client, financials, filings).
- `src/report/` – Jinja2 templates and CSS for the PDF report.
- `reports/` – Generated PDFs.
- `run.py` – CLI entrypoint.
- `backend/` – FastAPI app: symbol suggest, report job start/status, PDF export, feedback, Google OAuth + JWT auth, rate limiting.
  - `backend/main.py` – All API routes; `slowapi` limiter (user-keyed when authenticated, IP-keyed otherwise)
  - `backend/db.py` – PostgreSQL connection pool and query helpers
  - `backend/auth.py` – Google OAuth2 flow, JWT create/verify, `get_current_user` dependency
  - `backend/cache.py` – Report cache backed by `reports` table (24h TTL for concall, 7-day TTL for no-concall)
  - `backend/section_feedback_store.py` – Per-section star ratings stored in `section_feedback` table
  - `backend/migrations/001_init.sql` – Initial schema (users, reports, feedback)
  - `backend/migrations/002_sessions.sql` – Sessions table (required for Google Auth)
  - `backend/migrations/003_error_logs.sql` – Error logs table
  - `backend/migrations/004_concall_transcripts.sql` – Concall transcript cache table
  - `backend/migrations/005_reports_requested_by_generation_ms.sql` – Extra columns on `reports` for cache writes
  - `backend/migrations/008_earnings_dates.sql` – Board-meeting intimation log + derived earnings date calendar
  - `backend/earnings_date_store.py` – Calendar reads/writes, YoY/QoQ peer resolution
- `src/data/nse_board_meetings.py` – NSE board-meeting fetch and fiscal-period attribution
- `scripts/refresh_earnings_calendar.py` – Populates the calendar (Render Cron Job; see § Results Calendar)
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
