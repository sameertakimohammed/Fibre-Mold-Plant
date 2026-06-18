import logging
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Minimum acceptable length for a signing secret.
MIN_SECRET_LEN = 32

# Exact-match placeholder secrets that ship in the repo / examples. These are
# publicly known, so any of them in production would let anyone on the LAN forge
# an admin JWT (HS256). Reject them outright in production.
# NOTE: the user's current working dev secret ("dev-secret-key-fmp-...") is a
# real 60-char value and is intentionally NOT in this list, so it passes.
PLACEHOLDER_SECRETS = {
    "CHANGE-ME-IN-PRODUCTION-use-a-long-random-string",
    "change-me-please-use-a-long-random-string",
    "change_this_to_a_long_random_string",
}

# Substrings that always indicate a placeholder, regardless of surrounding text
# (case-insensitive). Kept deliberately narrow so a genuine secret can't trip it.
PLACEHOLDER_SUBSTRINGS = ("change-me", "changeme")

# Known placeholder/weak DB passwords and admin passwords shipped in examples.
PLACEHOLDER_DB_PASSWORDS = {
    "fmp_password",
    "change_this_db_password",
    "change-me-please",
}
PLACEHOLDER_ADMIN_PASSWORDS = {
    "admin123",
    "admin",
    "password",
    "changeme",
}

_GENERATE_HINT = (
    'generate a strong one with: '
    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
)


def _is_placeholder_secret(value: str) -> bool:
    if value in PLACEHOLDER_SECRETS:
        return True
    low = value.lower()
    return any(sub in low for sub in PLACEHOLDER_SUBSTRINGS)


class Settings(BaseSettings):
    # Environment: "production" (default) enforces strong secrets and refuses to
    # start on placeholder/short values. Set APP_ENV=development to relax for
    # local dev (e.g. SQLite). Overridable via the APP_ENV env var.
    app_env: str = "production"

    # Database
    database_url: str = "postgresql+psycopg://fmp:fmp_password@db:5432/fmp"

    # Auth
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-a-long-random-string"
    algorithm: str = "HS256"
    # IMPORTANT: this plant runs 12-hour shifts and there is NO refresh-token
    # flow yet, so a short access-token lifetime would log operators out
    # mid-shift. Keep this shift-friendly default (12h). Token *revocation*
    # (password_changed_at + is_active checks in deps.get_current_user) is the
    # real security win, not a short expiry. Once TLS + an httpOnly refresh
    # cookie are in place, this can safely be dropped to ~30-60 min.
    access_token_expire_minutes: int = 60 * 12  # 12h shift-friendly

    # --- Login lockout (brute-force + AD account protection) ---
    # After this many consecutive failed logins, a KNOWN user is locked.
    lockout_threshold: int = 5
    # How long (minutes) the account stays locked; auto-unlocks after this.
    lockout_minutes: int = 15

    # App
    project_name: str = "Fibre Mold Plant"
    first_admin_username: str = "admin"
    first_admin_password: str = "admin123"  # forced change on first login is recommended
    first_admin_name: str = "Plant Administrator"

    # Active Directory (LDAP) — leave AD_ENABLED=false to use local passwords only
    ad_enabled: bool = False
    ad_server: str = ""          # e.g. 192.168.1.10  or  dc01.golden.com.fj
    ad_domain: str = ""          # e.g. golden.com.fj
    ad_base_dn: str = ""         # e.g. DC=golden,DC=com,DC=fj  (used for group lookup, optional)
    ad_local_bypass: str = "admin"  # comma-separated usernames that always use local password
    # AD group -> app role mapping. Comma-separated "GroupCN=role" pairs, e.g.
    #   "Fibre-Admins=admin,Fibre-Supervisors=supervisor,Fibre-Operators=operator"
    # When set, after a successful AD bind we read the user's memberOf groups
    # under ad_base_dn, resolve the HIGHEST mapped role, and re-sync the user's
    # role on every login. When EMPTY (default), we keep the legacy behaviour:
    # auto-provision new AD users as operator and leave the role app-managed.
    ad_group_role_map: str = ""
    # When True AND ad_group_role_map is set: a user in NONE of the mapped
    # groups is denied (is_active set False). When False, an unmapped AD user
    # keeps their current role and access.
    ad_group_strict: bool = False

    # ── Scheduler (APScheduler, in-process) ────────────────────────────────
    # Master switch for the in-process BackgroundScheduler started in the
    # FastAPI lifespan. On by default. NOTE: this deployment runs uvicorn with a
    # SINGLE worker, so exactly one scheduler exists. If you ever scale to
    # multiple workers/replicas, set SCHEDULER_ENABLED=false on all but ONE so
    # the daily jobs don't run N times.
    scheduler_enabled: bool = True
    # Hour (0-23, local server time) the daily alert-evaluation job runs.
    alert_scan_hour: int = 6

    # ── Alert thresholds ───────────────────────────────────────────────────
    # Defaults mirror analytics._build_insights so dashboard insights and
    # proactive alerts agree. All overridable via env.
    # Heavy-downtime day: a single day losing >= this many minutes (4h = 240).
    alert_heavy_downtime_min: float = 240
    # Period downtime rate (% of scheduled) at/above which we warn.
    alert_downtime_pct: float = 12.0
    # A day's fuel efficiency worse than this multiple of the period average
    # (L/1k trays) is flagged as a poor-efficiency outlier.
    alert_fuel_eff_mult: float = 1.4
    # A producing day below this fraction of the period's average/day is "low".
    alert_low_output_frac: float = 0.6
    # Period re-pulp / reject rate (%) at/above which we warn.
    alert_reject_pct: float = 4.0
    # How many trailing days the daily scan / post-write evaluation considers.
    alert_window_days: int = 14
    # A 'missed shift' alert fires if a day in the recent window (older than
    # this many days back, to allow late entry) has fewer than the expected
    # number of shift entries. Best-effort heuristic.
    alert_missed_shift_grace_days: int = 1
    alert_expected_shifts_per_day: int = 1

    # ── Email / SMTP (Microsoft 365 / Exchange) — DEFAULT OFF ──────────────
    # Nothing is sent until smtp_enabled is True AND host/from/recipients are
    # set. send_email() no-ops (with a logged warning) when incomplete, so the
    # app is safe to run unconfigured.
    smtp_enabled: bool = False
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_starttls: bool = True
    # Comma-separated recipient lists.
    alert_email_to: str = ""    # who receives warn/critical alert emails
    report_email_to: str = ""   # who receives the scheduled .xlsx report
    # Per-dedup-key cooldown (minutes) so the same alert doesn't email twice.
    alert_email_cooldown_min: int = 720  # 12h

    # ── Scheduled report email ─────────────────────────────────────────────
    # Cadence for the automatic report email. "monthly" (1st of month, prior
    # month), "weekly" (Monday, prior 7 days), or "off" to disable.
    report_email_cadence: str = "monthly"
    # Hour (0-23) and, for monthly, day-of-month the report job runs.
    report_email_hour: int = 7
    report_email_day_of_month: int = 1

    class Config:
        env_file = ".env"
        extra = "ignore"

    @model_validator(mode="after")
    def _enforce_secure_config(self) -> "Settings":
        """Fail-closed config validation.

        In production, refuse to start on insecure secrets/passwords. Outside
        production we only warn, so local/dev (SQLite, placeholder values) still
        boots freely.
        """
        is_prod = self.app_env.strip().lower() == "production"

        # --- SECRET_KEY (most important: signs HS256 JWTs) ---
        secret_problem = None
        if _is_placeholder_secret(self.secret_key):
            secret_problem = (
                "SECRET_KEY is set to a known placeholder value."
            )
        elif len(self.secret_key) < MIN_SECRET_LEN:
            secret_problem = (
                f"SECRET_KEY is too short ({len(self.secret_key)} chars); "
                f"it must be at least {MIN_SECRET_LEN} characters."
            )

        # --- DB / admin passwords (best-effort, where reachable) ---
        db_problem = None
        if self.first_admin_password in PLACEHOLDER_ADMIN_PASSWORDS:
            db_problem = (
                f"ADMIN_PASSWORD is set to a weak/placeholder value "
                f"('{self.first_admin_password}'). Set a strong ADMIN_PASSWORD in .env."
            )
        # DB password is embedded in database_url; flag only obvious placeholders.
        weak_db_pw = next(
            (pw for pw in PLACEHOLDER_DB_PASSWORDS if f":{pw}@" in self.database_url),
            None,
        )
        if weak_db_pw is not None:
            db_problem = (db_problem + " " if db_problem else "") + (
                f"DB_PASSWORD is set to a known placeholder ('{weak_db_pw}'). "
                "Set a strong DB_PASSWORD in .env."
            )

        # Weak DB/admin passwords are advisory only — they are never fatal, so the
        # app always boots with the current live .env (which still ships
        # ADMIN_PASSWORD=admin123, flagged for forced change on first login).
        if db_problem:
            logger.warning(
                "[config] weak credential — change it as soon as possible: %s", db_problem
            )

        if not is_prod:
            if secret_problem:
                logger.warning(
                    "[config] insecure SECRET_KEY (allowed in non-production): %s",
                    secret_problem,
                )
            return self

        # Production: SECRET_KEY problems are always fatal (HS256 JWT forgery risk).
        if secret_problem:
            raise ValueError(
                f"{secret_problem} The app refuses to start in production with an "
                f"insecure SECRET_KEY. Set a strong SECRET_KEY in .env — {_GENERATE_HINT}"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
