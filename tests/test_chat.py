import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)


def test_chat_returns_gross_margin_with_sources():
    response = client.post(
        "/api/v1/chat",
        json={
            "company_id": "NWI",
            "fiscal_year": 2024,
            "fiscal_quarter": 3,
            "question": "What is the gross margin?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["kpi_name"] == "Gross margin"
    assert data["value"] is not None
    assert data["confidence"] == "high"
    assert "R900279" in data["source_row_ids"]
    assert "R900277" in data["source_row_ids"]


def test_chat_withholds_missing_rd_intensity():
    response = client.post(
        "/api/v1/chat",
        json={
            "company_id": "ZLG",
            "fiscal_year": 2024,
            "fiscal_quarter": 3,
            "question": "What is the R&D intensity?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["value"] is None
    assert data["confidence"] == "low"
    assert data["source_row_ids"] == []
    assert "withheld" in data["answer"].lower()


def test_chat_rejects_unknown_company():
    response = client.post(
        "/api/v1/chat",
        json={
            "company_id": "XXX",
            "fiscal_year": 2024,
            "fiscal_quarter": 3,
            "question": "What is the gross margin?",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COMPANY_NOT_FOUND"
