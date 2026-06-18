# Backend test suite

A contract + RBAC regression suite that runs **fully offline** against a
throwaway SQLite database. It never touches Postgres, the real `dev.db`, Docker,
or the running app — `conftest.py` sets the environment (a temp-file SQLite DB,
`APP_ENV=development`, scheduler/AD/SMTP off, a known admin password) **before**
the app is imported, then drives it through `fastapi.testclient.TestClient`. The
app lifespan creates the tables on the SQLite path and seeds the admin user.

## What is covered

- `test_auth.py` — login success returns a token; wrong/unknown password → 401;
  account lockout trips to 429 after `LOCKOUT_THRESHOLD` failures; `/api/auth/me`
  needs a valid token (401 without).
- `test_rbac.py` — the operator/supervisor/manager/admin permission matrix
  (exact status codes), derived from the `require_role` decorators in the routers.
- `test_shifts.py` — create; duplicate `(work_date, shift)` → 409; soft-delete
  then re-create the same slot; negative numeric field → 422.
- `test_users.py` — duplicate username → 409; `<6` char password → 422; username
  is lowercased.
- `test_audit.py` — an authenticated write appears in `GET /api/audit` with the
  right `actor_username`; `GET /api/audit/verify` returns `ok: true`.
- `test_contract.py` — a stable allow-list assertion over `app.openapi()` paths
  so an accidental route removal/rename fails the suite.

## How to run

The suite must run from a context where `app` (i.e. `backend/app`) is importable.

### In the Docker container (ad hoc, no rebuild)

```bash
docker compose exec app pip install pytest==8.3.4 httpx==0.28.1
docker compose exec app python -m pytest          # cwd is the backend WORKDIR
```

### Locally in a virtualenv

From the `backend/` directory:

```bash
python -m venv .venv-test
.venv-test/Scripts/activate      # Windows;  source .venv-test/bin/activate on *nix
pip install -r requirements.txt
python -m pytest                 # pytest.ini sets testpaths=tests
```

If you run pytest from outside `backend/`, point Python at it:

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```
