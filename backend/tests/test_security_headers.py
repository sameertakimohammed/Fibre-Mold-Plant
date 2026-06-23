"""Defense-in-depth HTTP response headers are present on every response."""


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    h = r.headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in h.get("Referrer-Policy", "")
    assert h.get("Strict-Transport-Security", "").startswith("max-age=")
    csp = h.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
