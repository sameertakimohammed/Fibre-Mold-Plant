# CONTINUE — Developer Handoff

This is a working, tested full-stack app. Everything below is what you need to keep
building it in your own editor. Read this once, then use it as a map.

---

## TL;DR — get it running locally in 5 minutes (no Docker)

You need **Python 3.11+** and **Node 18+**.

**Terminal 1 — backend** (uses SQLite locally so you don't need Postgres while developing):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DATABASE_URL="sqlite:///./dev.db" uvicorn app.main:app --reload --port 8000
```

On first start it creates the admin user and imports the May data automatically.
API docs are live at http://localhost:8000/docs

**Terminal 2 — frontend** (hot-reloads as you edit):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` to port 8000, so
login and all data work. Sign in `admin` / `admin123`.

> SQLite vs Postgres: the app runs on either. Locally, SQLite is zero-setup.
> In production (`docker compose up`) it uses Postgres. Same code, same models.
> The one difference: SQLite needs `connect_args={"check_same_thread": False}`,
> which `app/core/database.py` already handles when the URL starts with `sqlite`.

---

## How it fits together

```
frontend (React/Vite)  ──/api──>  backend (FastAPI)  ──SQL──>  Postgres / SQLite
   src/pages/*.jsx                  app/routers/*.py            app/models/*.py
   src/api/client.js                app/main.py                 (one table per file)
```

- **Auth**: login returns a JWT. Frontend stores it in `localStorage` (`src/api/client.js`)
  and sends it as `Authorization: Bearer`. Backend validates in `app/deps.py`.
- **Roles**: operator < supervisor < manager < admin. Guarded by `require_role()`
  in `app/deps.py`; the UI also hides controls per role.
- **Analytics**: all KPI math is server-side in `app/routers/analytics.py` → `/api/analytics/summary`.
  The frontend pages just render what it returns. **If you add a metric, add it here first.**

---

## Where everything lives

| You want to… | Edit |
|---|---|
| Add/change a DB field | `backend/app/models/*.py` then matching `schemas/operations.py` |
| Add an API endpoint | `backend/app/routers/` (register it in `app/main.py`) |
| Change a KPI or chart's data | `backend/app/routers/analytics.py` |
| Change a page's look/charts | `frontend/src/pages/*.jsx` |
| Add an API call from the UI | `frontend/src/api/client.js` |
| Change colors/spacing | `frontend/src/index.css` (CSS vars at top) |
| Add a nav item | `frontend/src/App.jsx` (the `nav` array in `Sidebar`) |
| Change seed/import behavior | `backend/app/services/seed.py`, `import_excel.py`, `import_history.py` |
| Change the Month End Report layout | `backend/app/services/report_monthend.py` |
| Change AI commentary / Q&A behavior | `backend/app/services/ai.py` (prompts, context, model) |

---

## Database migrations (important before you change models)

Right now the app uses `Base.metadata.create_all()` (in `app/main.py` lifespan),
which **creates tables but does not alter existing ones**. That's fine for new
installs, but once you have real data and want to change a column, add Alembic:

```bash
cd backend
pip install alembic
alembic init alembic
# in alembic/env.py: set target_metadata = Base.metadata  and import your models
# set sqlalchemy.url from env (or hardcode for dev)
alembic revision --autogenerate -m "add new field"
alembic upgrade head
```

Then remove (or keep as a fallback) the `create_all` call. Until you have
production data you care about, you can keep using `create_all` and just delete
`dev.db` when models change.

---

## What's done vs. what's next

### Done & tested
- Auth, JWT, 4 roles with enforced permissions (operator blocked from delete, etc.)
- Models + CRUD: production shifts, deliveries, bales, fuel dips, monthly stock, users
- Analytics endpoint feeding all dashboards
- Pages: Login, Dashboard, Production, Fuel, Downtime, Deliveries, LogShift, Account, Users
- Seed import of May data on first boot; Excel importer for future months
- Docker Compose deployment (frontend build + backend + Postgres)
- Verified end-to-end in a browser: login → log shift → persists → shows on dashboards

### Done since handoff
- **Entry forms for the other logs.** All four are wired up via a reusable
  `frontend/src/components/EntryForm.jsx` (field-spec driven):
  - Deliveries → "Record a Delivery" form on `pages/Deliveries.jsx` (+ role-gated
    Delete on each log row, supervisor+).
  - Fuel dips → "Record a Fuel Dip" form + dip log table on `pages/Fuel.jsx`.
  - Bale receipts + Monthly stock → new `pages/Materials.jsx` ("Stock & Bales" nav
    item). The month-end stock card pre-fills the selected period's existing values
    and upserts (supervisor+ can edit; others see it read-only).
  - `client.js` gained `deleteDelivery`, `listBales`/`createBale`,
    `listFuelDips`/`createFuelDip`, `listStock`/`upsertStock`.

- **UI + app overhaul.**
  - *Design system* — refreshed `index.css` (depth, gradients, refined KPI cards,
    sectioned sidebar). New shared components in `components/ui.jsx`: `Kpi` with trend
    delta + SVG `Spark`line, `Modal`, `PageSkeleton`, `Empty`. Toast system in
    `context/ToastContext.jsx` (`useToast().ok/err/info`) — all forms now toast.
  - *Responsive nav* — `App.jsx` has a fixed desktop sidebar that becomes a slide-in
    drawer with a hamburger topbar + scrim below 1000px (replaces the old scroll row).
  - *Date-range filtering* — `components/Period.jsx` `usePeriod()` now returns
    `{ start, end, rangeKey, control }` with a Month | Range toggle. Pages depend on
    `rangeKey`. (Materials stays month-only via the exported `PeriodPicker`.)
  - *Dashboard insights* — `/analytics/summary` now returns `deltas` (vs the previous
    equal-length window, drives KPI trend arrows) and `insights` (auto-flagged
    downtime/fuel/output/reject alerts → "Needs Attention" panel). Output chart has an
    average reference line. "⤓ Export" downloads the xlsx report.
  - *Report export* — `routers/reports.py` → `GET /api/reports/monthly.xlsx` (openpyxl,
    3 sheets: Summary, Shift Detail, Deliveries). Frontend `api.downloadReport()`.
  - *Shift log edit/delete/search* — `pages/Production.jsx` has a search box + a role-
    gated edit modal (supervisor+) and delete (manager+). Shift field layout shared via
    `components/shiftFields.js` (used by LogShift + the modal).

### Historical data + Month End Report (added)
- **Full history import.** `services/import_history.py` parses the plant's
  emailed monthly bundle — daily tracker, deliveries, fuel-dip, bale and the
  "End of Month Report" stock file — into one de-duplicated `data/history.json`
  (Aug 2024 → May 2026: ~985 shifts, 194 deliveries, 356 fuel dips, 595 bale
  receipts, 14 month-end records). `run_seed()` replays it on first boot,
  idempotently (gated by `SEED_HISTORY`, default on; the test suite sets it off).
  To regenerate the JSON from raw files:
  `python -m app.services.import_history build <src_dir> data/history.json`
  (point `<src_dir>` at a folder of the monthly .xlsx files; parsers find the
  header rows / sections by content, so the 2024 and 2026 layout drift is handled).
- **Month End Report.** `services/report_monthend.py` rebuilds the plant's
  emailed 10-section management template (diesel, goods produced, balance stock
  by colour, toner, label brands, pallets local/export, bales) as xlsx + pdf,
  rendered from `MonthlyStock.detail` (the full parsed payload — new JSON column,
  see migration `e5f6a7b8c9d0`) with computed fallbacks from production. Reached
  via `GET /api/v1/reports/report.{xlsx,pdf}?period=MonthEnd` and the two
  "Month End" buttons on the Reports page (monthly cadence).

### AI assistant (Claude) — added, default off
- **`services/ai.py`** — Anthropic SDK (`claude-opus-4-8`, adaptive thinking).
  `ai_available()` gates everything on `AI_ENABLED` + `ANTHROPIC_API_KEY`.
  `generate_commentary(data)` writes the "Plant Manager's Commentary" embedded in
  the Month End Report (xlsx + pdf); `answer_question(q, db)` powers Q&A, grounded
  in `collect_context(db)` — a bounded ~18-month digest of the plant's own
  production/deliveries/stock (aggregated in Python, never raw rows).
- **`routers/ai.py`** — `GET /api/v1/ai/status`, `POST /api/v1/ai/ask`
  (rate-limited 20/min), `GET /api/v1/ai/commentary`. All 503 when AI is off.
- **Frontend** — `components/AskAI.jsx` ("Ask the plant data") + a commentary card
  on the Reports page, both shown only when `/ai/status` reports enabled.
- Sends aggregated figures to Anthropic, so it's OFF by default. Turn on with
  `AI_ENABLED=true` + `ANTHROPIC_API_KEY` (see `.env.example`). Degrades
  gracefully — a failed/slow AI call just omits the commentary; the report still
  builds.

### Next up (suggested order)
1. **Alembic migrations** (see above) before the first real schema change.
2. **Validation polish.** e.g. fuel_use should reconcile with open−close; warn if
   product-type sum ≠ total qty.
3. **PDF report** option alongside the xlsx export.
4. **Inline edit for deliveries/bales/fuel/stock** rows (only shift log has edit so far).

---

## Testing

There are no automated tests yet — add them with:

```bash
cd backend
pip install pytest httpx
```

The pattern I used for manual integration testing (point it at SQLite, drive the
TestClient): create `tests/test_api.py`, patch `DATABASE_URL` to a temp sqlite file
before importing `app.main`, then exercise `/api/auth/login` → grab token → hit
endpoints. Worth formalizing as your first test file.

---

## Gotchas I already hit (so you don't)

- **bcrypt/passlib**: pin `bcrypt==4.0.1`. Newer 4.1+/4.2 throws a
  `module 'bcrypt' has no attribute '__about__'` warning with passlib 1.7.4.
  Already pinned in `requirements.txt`.
- **Duplicate date+shift**: there's a unique constraint on `(work_date, shift)`.
  The importer dedupes; the API returns 409 on a duplicate. Keep that contract.
- **Original Excel quirks**: some May rows had repeated date+shift and a couple of
  out-of-range fuel values; the importer skips dupes but does not clean outliers.
- **CORS is wide open** (`allow_origins=["*"]`) for local-network use. Tighten in
  `app/main.py` if you ever expose this beyond the plant.
- **Secrets**: `SECRET_KEY`, `DB_PASSWORD`, admin password all come from env
  (`.env` for Docker). Change them before real deployment.

---

## Deploy to the plant PC

See `README.md`. Short version: install Docker, `cp .env.example .env` and edit,
`docker compose up -d --build`, open `http://<pc-ip>:8000`.
