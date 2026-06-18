# Fibre Mold Plant — Production App

A multi-user web application for **Golden Manufactures' Fibre Mold Plant** (egg-tray
production). Shift operators log production from any device on the plant network;
supervisors and managers see live, synced dashboards. All data lives in one shared
database so nothing is re-keyed across spreadsheets.

---

## What's inside

- **Production dashboards** — output by tray type, hot-press utilisation, line speed
- **Fuel & energy** — daily diesel, efficiency (L per 1,000 trays), live cost estimate
- **Downtime** — causes classified from shift notes, % by shift, worst stoppages
- **Deliveries & stock** — produced-vs-delivered flow, by customer, month-end balance
- **Shift logging** — operators enter end-of-shift figures; everything updates instantly
- **Accounts & roles** — operator / supervisor / manager / admin, with enforced permissions

Your **May 2026** data is imported automatically on first start.

---

## Requirements

A single PC or small server on the plant network with **Docker** installed
(Docker Desktop on Windows/Mac, or Docker Engine on Linux). Nothing else.

---

## First-time setup

1. Copy the settings template and edit it:

   ```bash
   cp .env.example .env
   ```

   Open `.env` and set, at minimum, a strong `DB_PASSWORD` and `SECRET_KEY`.
   Generate a secret with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Start everything:

   ```bash
   docker compose up -d --build
   ```

   The first run downloads images, builds the app, starts PostgreSQL, creates the
   admin account, and imports the May data. Give it a minute.

3. Open the app from any device on the network:

   ```
   http://<plant-pc-ip>:8000
   ```

   (Find the PC's IP with `ipconfig` on Windows or `ip addr` on Linux.)

4. Sign in with the admin account from your `.env`
   (default `admin` / `admin123`) and set a new password when prompted.

The app **auto-starts on boot** (`restart: unless-stopped`), so it comes back
after a power cut without anyone logging in.

---

## Day-to-day use

- **Operators**: Log Shift → fill figures → Save. Done.
- **Supervisors**: can also edit recent shifts.
- **Managers**: full analytics, can delete records.
- **Admin**: Team & Access page to add staff and set roles.

Add a team member: sign in as admin → **Team & Access** → fill the form. They get a
temporary password and are forced to change it on first login.

---

## Importing a past month from Excel

If you have older tracker spreadsheets to load:

```bash
docker compose exec app python -m app.services.import_excel /path/inside/container.xlsx
```

Or copy the file in first:

```bash
docker compose cp ./TRACKER_JUNE_2026.xlsx app:/tmp/june.xlsx
docker compose exec app python -m app.services.import_excel /tmp/june.xlsx
```

Already-present date+shift rows are skipped, so re-running is safe.

---

## Backups

All data is in the `fmp_pgdata` Docker volume. To back it up:

```bash
docker compose exec db pg_dump -U fmp fmp > backup_$(date +%Y%m%d).sql
```

Keep these backups somewhere off the plant PC (a USB drive or network share).

To restore:

```bash
cat backup_YYYYMMDD.sql | docker compose exec -T db psql -U fmp fmp
```

---

## Common commands

| Task | Command |
|------|---------|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| View logs | `docker compose logs -f app` |
| Rebuild after code changes | `docker compose up -d --build` |
| Restart just the app | `docker compose restart app` |

---

## Architecture

```
Browser (operators / managers)
        │  http://plant-pc:8000
        ▼
┌─────────────────────────────┐
│  app container               │
│  • FastAPI (REST + JWT auth) │
│  • Serves built React UI     │
└──────────────┬──────────────┘
               │ SQL
               ▼
┌─────────────────────────────┐
│  db container — PostgreSQL   │
│  volume: fmp_pgdata          │
└─────────────────────────────┘
```

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, JWT auth (`backend/app/`)
- **Frontend**: React + Vite + Chart.js (`frontend/src/`), built into static files
- Both run from one container; Postgres runs alongside.

---

## Project layout

```
fmp-app/
├── docker-compose.yml      # orchestrates app + database
├── Dockerfile              # builds frontend, then backend image
├── .env.example            # copy to .env and edit
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # FastAPI entry, serves API + UI
│       ├── models/         # database tables
│       ├── schemas/        # request/response validation
│       ├── routers/        # API endpoints (auth, shifts, analytics, …)
│       ├── core/           # config, db, security
│       ├── services/       # seed + Excel importer
│       └── deps.py         # auth & role guards
│   └── data/               # original May data (imported on first run)
└── frontend/
    └── src/
        ├── pages/          # Dashboard, Production, Fuel, Downtime, …
        ├── components/
        ├── context/        # auth state
        └── api/            # API client + chart config
```

---

## Power BI / BI reporting

The database exposes a small set of **read-only views** as a stable contract for
Power BI (or any SQL client). Always query the **views**, never the base tables:
the views exclude soft-deleted records and shield reports from internal column
changes, and their derived KPIs use the **same formulas as the dashboard**, so
the numbers match.

**Views available** (all exclude soft-deleted rows):

| View | Grain | Key columns |
|------|-------|-------------|
| `vw_daily_production` | one row per `work_date` | `total_qty`, per-product totals (`p30s`…`p2cup`), `trays_from_products`, `fuel_use`, `downtime_min`, `sched_hours`, `repulped`, `fuel_eff` (L/1000 trays), `downtime_pct`, `reject_rate` |
| `vw_deliveries` | one row per delivery | `work_date`, `company`, `tray30`, `tray12n`, `tray12ff`, `pallets`, `total_trays` |
| `vw_fuel` | one row per fuel dip | `work_date`, `shift`, `open_dip`, `close_dip`, `actual_usage`, `received` |
| `vw_downtime` | one row per shift | `work_date`, `shift`, `downtime_min`, `comment`, `cause` (classified) |

> `total_qty` is the plant's headline tray count (the stored `qty` figure, the
> same number the dashboard KPIs use). `trays_from_products` is the sum of the
> per-product columns, provided for cross-checking. The `fuel_eff`,
> `downtime_pct`, and `reject_rate` columns are computed from `total_qty` /
> `sched_hours` exactly as the analytics endpoint does.

The views are created by an Alembic migration and are present automatically once
`docker compose up -d --build` has applied migrations. An admin can confirm the
layer exists at **`GET /api/integrations/bi/status`** (admin login required).

### Enable the read-only role

A NOLOGIN role **`fmp_readonly`** is created by the migration with `SELECT` on
the four views (and `USAGE` on the schema). **No password is stored in code or
migrations — by design.** The admin enables login and sets a password *out of
band*, once, from the DB container:

```bash
docker compose exec db psql -U fmp -d fmp -c "ALTER ROLE fmp_readonly WITH LOGIN PASSWORD 'choose-a-strong-password';"
```

(To rotate it later, run the same `ALTER ROLE ... PASSWORD '...'` again.)

### Point Power BI at it (LAN only)

Postgres listens on the plant network only — do **not** expose port 5432 to the
internet. To let Power BI on another PC reach it over the LAN, publish the DB
port in `docker-compose.yml` (e.g. add `ports: ["5432:5432"]` to the `db`
service) and ensure the Windows firewall allows it on the local subnet.

In Power BI Desktop → **Get Data → PostgreSQL database**:

| Setting | Value |
|---------|-------|
| Server | `<plant-pc-ip>:5432` |
| Database | `fmp` |
| Data Connectivity mode | Import (or DirectQuery) |
| Username | `fmp_readonly` |
| Password | the one you set with `ALTER ROLE` above |

Then select the four `vw_*` views in the Navigator. Because `fmp_readonly` only
has `SELECT` on the views, reports can never modify plant data.

---

## Security notes

- Change `SECRET_KEY`, `DB_PASSWORD`, and the admin password before real use.
- This is built for a **trusted local network**. If you ever expose it to the
  internet, put it behind HTTPS (a reverse proxy like Caddy or nginx) and tighten
  the CORS setting in `backend/app/main.py`.
