from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)


def test_stream_endpoint_returns_sse_events():
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "company_id": "NWI",
            "fiscal_year": 2024,
            "fiscal_quarter": 3,
            "question": "What is the gross margin?"
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: done" in response.text
    assert "event: token" in response.text


def test_stream_endpoint_has_no_cache():
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "company_id": "NWI",
            "fiscal_year": 2024,
            "fiscal_quarter": 3,
            "question": "What is the gross margin?"
        },
    )

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"
