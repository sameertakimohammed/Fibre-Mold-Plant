"""Backup visibility: the pure scan helper and the admin endpoint's role gate."""
import gzip
import os

import pytest

from app.services.backups import backup_status


def test_backup_status_missing_dir(tmp_path):
    s = backup_status(str(tmp_path / "does-not-exist"), 36)
    assert s["configured"] is False
    assert s["latest"] is None
    assert s["count"] == 0


def test_backup_status_empty_dir(tmp_path):
    s = backup_status(str(tmp_path), 36)
    assert s["configured"] is True
    assert s["count"] == 0
    assert s["latest"] is None
    assert s["stale"] is None


def test_backup_status_with_dump(tmp_path):
    # Mirror the sidecar layout: daily/<file>.sql.gz
    daily = tmp_path / "daily"
    daily.mkdir()
    dump = daily / "fmp-20260101-020000.sql.gz"
    with gzip.open(dump, "wb") as fh:
        fh.write(b"-- pg_dump\n")
    # A non-dump file must be ignored.
    (tmp_path / "README.txt").write_text("ignore me")

    s = backup_status(str(tmp_path), 36)
    assert s["configured"] is True
    assert s["count"] == 1
    assert s["latest"] is not None
    assert s["latest"]["name"].endswith("fmp-20260101-020000.sql.gz")
    assert s["latest"]["size_bytes"] > 0
    # Just-written file -> not stale.
    assert s["stale"] is False


def test_backup_status_flags_stale(tmp_path):
    dump = tmp_path / "fmp-old.sql.gz"
    with gzip.open(dump, "wb") as fh:
        fh.write(b"-- old\n")
    # Backdate mtime by 100 hours.
    old = os.path.getmtime(dump) - 100 * 3600
    os.utime(dump, (old, old))
    s = backup_status(str(tmp_path), 36)
    assert s["stale"] is True
    assert s["latest"]["age_hours"] >= 36


# ---- admin endpoint role gate ----
@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 403), ("admin", 200),
])
def test_backups_endpoint_admin_only(client, role_users, role, expected):
    r = client.get("/api/v1/admin/backups", headers=role_users[role]["headers"])
    assert r.status_code == expected, f"{role}: {r.status_code} {r.text}"
    if expected == 200:
        body = r.json()
        assert "configured" in body and "latest" in body
