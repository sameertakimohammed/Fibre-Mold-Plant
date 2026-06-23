#!/bin/sh
# Container entrypoint: wait for the database, adopt-or-upgrade the schema via
# Alembic, then start the API server.
#
# Adoption logic: if the DB has the application schema (users table) but no
# alembic_version table, it is a legacy pre-Alembic database — stamp it at the
# baseline so we adopt the existing schema WITHOUT recreating it. Then always
# run `alembic upgrade head` (no-op when current, full create on a fresh DB,
# applies future revisions otherwise).
set -e

cd /app

ALEMBIC="alembic -c /app/alembic.ini"

# --- 1. Wait for the database to accept connections (~30s max) ---
echo "[entrypoint] waiting for database..."
i=0
until python - <<'PY'
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings
try:
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 3})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    sys.exit(0)
except Exception as exc:
    print(f"[entrypoint]   db not ready: {exc}", file=sys.stderr)
    sys.exit(1)
PY
do
    i=$((i + 1))
    if [ "$i" -ge 15 ]; then
        echo "[entrypoint] ERROR: database not reachable after ~30s, giving up." >&2
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] database is up."

# --- 2. Adopt an existing pre-Alembic schema if present ---
# Prints "ADOPT" if users table exists AND alembic_version does NOT.
NEEDS_STAMP=$(python - <<'PY'
from sqlalchemy import create_engine, inspect
from app.core.config import settings
engine = create_engine(settings.database_url)
insp = inspect(engine)
tables = set(insp.get_table_names())
if "users" in tables and "alembic_version" not in tables:
    print("ADOPT")
else:
    print("OK")
PY
)

if [ "$NEEDS_STAMP" = "ADOPT" ]; then
    echo "[entrypoint] legacy schema detected (users present, no alembic_version) -> stamping baseline."
    $ALEMBIC stamp head
fi

# --- 3. Always upgrade to head (no-op if already current, creates on fresh DB) ---
echo "[entrypoint] applying migrations (alembic upgrade head)..."
$ALEMBIC upgrade head

# --- 4. Start the application ---
# --proxy-headers + forwarded-allow-ips: trust X-Forwarded-For/Proto from the
# reverse proxy (Traefik/Caddy) so the app sees the REAL client IP — needed for
# accurate audit-log IPs and correct per-client rate limiting. The app is only
# reachable via the proxy (no published port), so trusting all upstreams is safe.
echo "[entrypoint] starting uvicorn."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips="*"
