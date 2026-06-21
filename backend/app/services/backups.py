"""Backup visibility — scan the nightly pg_dump directory and report status.

The plant's backups are produced by the prodrigestivill/postgres-backup-local
sidecar (see docker-compose.yml), which writes gzip-compressed SQL dumps named
like ``fmp-YYYYMMDD-HHMMSS.sql.gz`` into daily/weekly/monthly subfolders of a
bind-mounted directory. This module scans that directory (recursively) so the
admin UI can answer "do we actually have a recent backup?" — a backup nobody
checks is a backup that isn't there.

Pure filesystem reads, no DB. Safe to call when the directory is absent (local
SQLite dev has no sidecar): it simply reports configured=False.
"""
import os
from datetime import datetime, timezone

# Dump file extensions the sidecar can produce (gzip plain-SQL by default).
_DUMP_SUFFIXES = (".sql.gz", ".sql", ".dump", ".sql.zst")


def _is_dump(name: str) -> bool:
    low = name.lower()
    return any(low.endswith(s) for s in _DUMP_SUFFIXES)


def backup_status(backup_dir: str, stale_hours: float) -> dict:
    """Summarize the backup directory.

    Returns a dict with: configured, dir, count, total_size_bytes, latest
    ({name, size_bytes, modified, age_hours}) and stale (bool|None).
    """
    base = (backup_dir or "").strip()
    result = {
        "configured": bool(base) and os.path.isdir(base),
        "dir": base,
        "count": 0,
        "total_size_bytes": 0,
        "latest": None,
        "stale": None,
        "stale_hours": stale_hours,
    }
    if not result["configured"]:
        return result

    newest_path = None
    newest_mtime = -1.0
    total = 0
    count = 0
    for root, _dirs, files in os.walk(base):
        for fname in files:
            if not _is_dump(fname):
                continue
            path = os.path.join(root, fname)
            try:
                st = os.stat(path)
            except OSError:
                continue
            count += 1
            total += st.st_size
            if st.st_mtime > newest_mtime:
                newest_mtime = st.st_mtime
                newest_path = path

    result["count"] = count
    result["total_size_bytes"] = total
    if newest_path is not None:
        modified = datetime.fromtimestamp(newest_mtime, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - modified).total_seconds() / 3600
        result["latest"] = {
            "name": os.path.relpath(newest_path, base),
            "size_bytes": os.path.getsize(newest_path),
            "modified": modified.isoformat(),
            "age_hours": round(age_hours, 1),
        }
        result["stale"] = age_hours > stale_hours
    return result
