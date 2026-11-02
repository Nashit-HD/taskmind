from fastapi.testclient import TestClient


def test_health_is_200_when_the_database_answers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_needs_no_token(client: TestClient) -> None:
    assert "Authorization" not in client.headers
    assert client.get("/health").status_code == 200
