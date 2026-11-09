from fastapi.testclient import TestClient

from ticket_api.main import create_app


def test_ticket_lifecycle_and_status_filter(tmp_path):
    app = create_app(tmp_path / "tickets.db")
    with TestClient(app) as client:
        created = client.post(
            "/tickets",
            json={"title": "Wi-Fi is unavailable", "description": "Library building"},
        )

        assert created.status_code == 201
        ticket = created.json()
        assert ticket["status"] == "open"
        assert ticket["title"] == "Wi-Fi is unavailable"

        updated = client.patch(f"/tickets/{ticket['id']}", json={"status": "in_progress"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "in_progress"

        filtered = client.get("/tickets", params={"status": "in_progress"})
        assert [item["id"] for item in filtered.json()] == [ticket["id"]]
        assert client.get("/tickets", params={"status": "resolved"}).json() == []


def test_validation_and_missing_ticket_responses(tmp_path):
    app = create_app(tmp_path / "tickets.db")
    with TestClient(app) as client:
        assert client.post("/tickets", json={"title": ""}).status_code == 422
        assert client.patch("/tickets/999", json={"status": "resolved"}).status_code == 404
        assert client.get("/tickets/999").status_code == 404
        assert client.patch("/tickets/999", json={"status": "unknown"}).status_code == 422


def test_health_checks_and_prometheus_metrics(tmp_path):
    app = create_app(tmp_path / "tickets.db")
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        client.get("/tickets")

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "http_requests_total" in metrics.text
        assert "http_request_duration_seconds" in metrics.text
