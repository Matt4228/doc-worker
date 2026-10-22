
import pytest

from main import app

PROTECTED_PREFIXES = ("/documents", "/chat")
SAMPLE_ID = "00000000-0000-0000-0000-000000000001"


def protected_routes():
    """Every (method, path) the app serves under /documents and /chat.

    Read from the OpenAPI schema (the public list of endpoints behind
    /docs) so a route added later is covered here too.
    """
    for path, operations in app.openapi()["paths"].items():
        if path.startswith(PROTECTED_PREFIXES):
            concrete = path.replace("{document_id}", SAMPLE_ID)
            for method in operations:
                yield method.upper(), concrete


def test_protected_routes_were_found():
    # Guards the test below: if the route discovery ever matched nothing,
    # the parametrized test would silently run zero cases and still pass.
    assert len(list(protected_routes())) >= 5


@pytest.mark.parametrize("method, path", list(protected_routes()))
def test_every_documents_and_chat_route_requires_the_password(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401


def test_missing_password_is_401_with_bearer_challenge(client):
    response = client.get("/auth/check")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_wrong_password_is_401(client):
    response = client.get("/auth/check", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_non_ascii_password_is_401_not_a_crash(client):
    # secrets.compare_digest raises TypeError on non-ASCII str, which would
    # surface as a 500 if the comparison weren't done on encoded bytes.
    # Sent as raw UTF-8 bytes: HTTP clients only accept ASCII header strings.
    response = client.get("/auth/check", headers={"Authorization": "Bearer pässwörd".encode()})
    assert response.status_code == 401


def test_correct_password_passes(client, auth_header):
    response = client.get("/auth/check", headers=auth_header)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_correct_password_reaches_a_real_route(client, auth_header, monkeypatch):
    from routes import documents

    class FakeConn:
        async def fetch(self, *args):
            return []

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, *exc):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(documents, "get_pool", fake_get_pool)
    response = client.get("/documents/", headers=auth_header)
    assert response.status_code == 200
    assert response.json() == []


def test_unset_password_refuses_everything(client, auth_header, monkeypatch):
    # Fails closed: a deploy that forgets DEMO_PASSWORD must not serve the API.
    monkeypatch.delenv("DEMO_PASSWORD")
    response = client.get("/auth/check", headers=auth_header)
    assert response.status_code == 503


def test_health_stays_open_for_the_host(client, monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD")
    response = client.get("/health")
    assert response.status_code == 200
