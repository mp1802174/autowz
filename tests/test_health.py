def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "autowz"
    assert "message" in data
