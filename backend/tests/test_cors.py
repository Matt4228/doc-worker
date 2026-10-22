from main import allowed_origins


def preflight(client, origin):
    return client.options(
        "/auth/check",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_local_frontend_may_send_the_password_header(client):
    response = preflight(client, "http://localhost:3000")
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_unknown_origin_is_not_allowed(client):
    response = preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origins_parses_a_comma_separated_list(monkeypatch):
    # Trailing slashes are trimmed: browsers send the Origin header without
    # one, so "https://x.vercel.app/" would otherwise never match.
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://a.vercel.app/ , http://localhost:3000,, ")
    assert allowed_origins() == ["https://a.vercel.app", "http://localhost:3000"]


def test_allowed_origins_defaults_to_local_dev(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert allowed_origins() == ["http://localhost:3000"]
