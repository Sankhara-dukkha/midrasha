from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_returns_user_without_password_hash(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"email": "A@Example.com", "password": PASSWORD, "display_name": "A"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "password" not in body and "password_hash" not in body
    # Zero-knowledge baseline.
    assert body["language_level_hebrew"] == 0
    assert body["language_level_arabic"] == 0
    assert body["language_level_farsi"] == 0
    assert body["track"] == "general"


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": PASSWORD, "display_name": "D"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_rejects_weak_or_invalid_input(client: TestClient) -> None:
    base = {"email": "x@example.com", "password": PASSWORD, "display_name": "X"}
    assert client.post("/api/auth/register", json={**base, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "x" * 73}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "email": "nope"}).status_code == 422
    assert (
        client.post("/api/auth/register", json={**base, "time_zone": "Mars/Olympus"}).status_code
        == 422
    )


def test_login_wrong_password_is_401(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/auth/login", json={"email": "recruit@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_is_401(client: TestClient) -> None:
    resp = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "x"})
    assert resp.status_code == 401


def test_me_requires_valid_token(client: TestClient) -> None:
    assert client.get("/api/user/me").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/user/me", headers=bad).status_code == 401


def test_me_and_update(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/user/me", headers=auth_headers).json()["display_name"] == "Recruit"

    resp = client.patch(
        "/api/user/me",
        headers=auth_headers,
        json={"time_zone": "Asia/Jerusalem", "language_level_farsi": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["time_zone"] == "Asia/Jerusalem"
    assert resp.json()["language_level_farsi"] == 1

    too_high = client.patch("/api/user/me", headers=auth_headers, json={"language_level_hebrew": 6})
    assert too_high.status_code == 422
