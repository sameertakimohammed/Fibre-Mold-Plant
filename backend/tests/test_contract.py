"""OpenAPI contract guard.

A STABLE ALLOW-LIST of (path, method) pairs the React frontend (and future
clients) depend on. We assert each expected route is still present, so an
accidental removal or rename fails the test. We deliberately do NOT freeze the
full schema or forbid extra routes, so adding a new endpoint won't break this.
"""
from app.main import app

# (path, HTTP method) pairs that MUST exist. Derived from the routers.
# The API is versioned under /api/v1; the infra health probes stay UNVERSIONED.
EXPECTED_ROUTES = {
    # auth
    ("/api/v1/auth/login", "post"),
    ("/api/v1/auth/me", "get"),
    ("/api/v1/auth/change-password", "post"),
    # users (admin)
    ("/api/v1/users", "get"),
    ("/api/v1/users", "post"),
    ("/api/v1/users/{user_id}", "patch"),
    ("/api/v1/users/{user_id}", "delete"),
    # shifts
    ("/api/v1/shifts", "get"),
    ("/api/v1/shifts", "post"),
    ("/api/v1/shifts/{shift_id}", "put"),
    ("/api/v1/shifts/{shift_id}", "delete"),
    # operations
    ("/api/v1/deliveries", "get"),
    ("/api/v1/deliveries", "post"),
    ("/api/v1/deliveries/{item_id}", "delete"),
    ("/api/v1/bales", "get"),
    ("/api/v1/bales", "post"),
    ("/api/v1/bales/{item_id}", "delete"),
    ("/api/v1/fuel-dips", "get"),
    ("/api/v1/fuel-dips", "post"),
    ("/api/v1/fuel-dips/{item_id}", "delete"),
    ("/api/v1/monthly-stock", "get"),
    ("/api/v1/monthly-stock/{period}", "put"),
    # analytics
    ("/api/v1/analytics/summary", "get"),
    ("/api/v1/analytics/periods", "get"),
    # reports
    ("/api/v1/reports/monthly.xlsx", "get"),
    # audit
    ("/api/v1/audit", "get"),
    ("/api/v1/audit/verify", "get"),
    # notifications
    ("/api/v1/notifications", "get"),
    ("/api/v1/notifications/{notification_id}/ack", "post"),
    # bi (admin)
    ("/api/v1/integrations/bi/status", "get"),
    # health (UNVERSIONED infra probes)
    ("/api/health", "get"),
    ("/api/health/ready", "get"),
}


def _actual_routes():
    paths = app.openapi()["paths"]
    return {(path, method.lower())
            for path, ops in paths.items()
            for method in ops}


def test_all_expected_routes_present():
    actual = _actual_routes()
    missing = EXPECTED_ROUTES - actual
    assert not missing, f"OpenAPI is missing expected routes: {sorted(missing)}"


def test_openapi_builds():
    schema = app.openapi()
    assert schema["info"]["title"]
    assert schema["paths"], "OpenAPI exposes no paths"
