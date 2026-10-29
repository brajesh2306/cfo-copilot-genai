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



def test_request_id_is_returned():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_validation_error_has_standard_body_and_request_id():
    response = client.post(
        "/api/v1/chat",
        json={
            "company_id": "NWI",
            "fiscal_year": 2024,
            "fiscal_quarter": 9,
            "question": "gross margin",
        },
    )

    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert data["request_id"]
    assert response.headers["X-Request-ID"] == data["request_id"]


def test_queued_request_runs_after_active_request_finishes():
    import asyncio
    from starlette.requests import Request
    from starlette.responses import Response
    import app.api as api

    async def run_test():
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_entered = asyncio.Event()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/health",
            "raw_path": b"/api/v1/health",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }

        original_limit = api.MAX_CONCURRENT_REQUESTS
        original_queue_limit = api.MAX_QUEUED_REQUESTS
        original_timeout = api.QUEUE_WAIT_TIMEOUT_SECONDS
        original_active = api._active_requests
        original_queued = api._queued_requests

        api.MAX_CONCURRENT_REQUESTS = 1
        api.MAX_QUEUED_REQUESTS = 1
        api.QUEUE_WAIT_TIMEOUT_SECONDS = 2
        api._active_requests = 0
        api._queued_requests = 0

        async def first_handler(request):
            first_entered.set()
            await release_first.wait()
            return Response("first")

        async def second_handler(request):
            second_entered.set()
            return Response("second")

        try:
            first_task = asyncio.create_task(
                api.add_request_id(Request(dict(scope)), first_handler)
            )
            await asyncio.wait_for(first_entered.wait(), timeout=1)

            second_task = asyncio.create_task(
                api.add_request_id(Request(dict(scope)), second_handler)
            )

            for _ in range(100):
                if api._queued_requests == 1:
                    break
                await asyncio.sleep(0.01)

            assert api._queued_requests == 1
            assert not second_entered.is_set()

            release_first.set()
            first_response, second_response = await asyncio.wait_for(
                asyncio.gather(first_task, second_task), timeout=2
            )

            assert first_response.status_code == 200
            assert second_response.status_code == 200
            assert second_entered.is_set()
            assert api._active_requests == 0
            assert api._queued_requests == 0
        finally:
            release_first.set()
            api.MAX_CONCURRENT_REQUESTS = original_limit
            api.MAX_QUEUED_REQUESTS = original_queue_limit
            api.QUEUE_WAIT_TIMEOUT_SECONDS = original_timeout
            api._active_requests = original_active
            api._queued_requests = original_queued

    asyncio.run(run_test())


def test_queued_request_timeout_returns_503_and_releases_queue_slot():
    import asyncio
    import json
    from starlette.requests import Request
    from starlette.responses import Response
    import app.api as api

    async def run_test():
        first_entered = asyncio.Event()
        release_first = asyncio.Event()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/health",
            "raw_path": b"/api/v1/health",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }

        original_limit = api.MAX_CONCURRENT_REQUESTS
        original_queue_limit = api.MAX_QUEUED_REQUESTS
        original_timeout = api.QUEUE_WAIT_TIMEOUT_SECONDS
        original_active = api._active_requests
        original_queued = api._queued_requests
        original_condition = api._request_condition
        api._request_condition = asyncio.Condition()

        api.MAX_CONCURRENT_REQUESTS = 1
        api.MAX_QUEUED_REQUESTS = 1
        api.QUEUE_WAIT_TIMEOUT_SECONDS = 0.05
        api._active_requests = 0
        api._queued_requests = 0

        async def first_handler(request):
            first_entered.set()
            await release_first.wait()
            return Response("first")

        async def second_handler(request):
            return Response("unexpected")

        try:
            first_task = asyncio.create_task(
                api.add_request_id(Request(dict(scope)), first_handler)
            )
            await asyncio.wait_for(first_entered.wait(), timeout=1)

            second_response = await api.add_request_id(
                Request(dict(scope)), second_handler
            )

            assert second_response.status_code == 503
            assert second_response.headers.get("Retry-After") == "1"
            assert json.loads(second_response.body)["detail"]["code"] == "SERVICE_BUSY"
            assert api._queued_requests == 0
            assert api._active_requests == 1

            release_first.set()
            await asyncio.wait_for(first_task, timeout=1)
            assert api._active_requests == 0
        finally:
            release_first.set()
            api.MAX_CONCURRENT_REQUESTS = original_limit
            api.MAX_QUEUED_REQUESTS = original_queue_limit
            api.QUEUE_WAIT_TIMEOUT_SECONDS = original_timeout
            api._active_requests = original_active
            api._queued_requests = original_queued
            api._request_condition = original_condition

    asyncio.run(run_test())

def test_overload_returns_503_and_retry_after():
    import asyncio
    from types import SimpleNamespace
    from starlette.requests import Request
    from starlette.responses import Response
    import app.api as api

    async def run_test():
        entered = asyncio.Event()
        release = asyncio.Event()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/health",
            "raw_path": b"/api/v1/health",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }

        first_request = Request(dict(scope))
        second_request = Request(dict(scope))

        original_limit = api.MAX_CONCURRENT_REQUESTS
        original_queue_limit = api.MAX_QUEUED_REQUESTS
        original_active = api._active_requests
        original_queued = api._queued_requests
        api.MAX_CONCURRENT_REQUESTS = 1
        api.MAX_QUEUED_REQUESTS = 0
        api._active_requests = 0
        api._queued_requests = 0

        async def slow_call_next(request):
            entered.set()
            await release.wait()
            return Response("ok")

        try:
            first_task = asyncio.create_task(
                api.add_request_id(first_request, slow_call_next)
            )
            await entered.wait()

            async def fast_call_next(request):
                return Response("unexpected")

            second_response = await api.add_request_id(
                second_request, fast_call_next
            )
            assert second_response.status_code == 503
            assert second_response.headers.get("Retry-After") == "1"
            assert second_response.headers.get("X-Request-ID")
            import json
            assert json.loads(second_response.body)["detail"]["code"] == "SERVICE_BUSY"

            release.set()
            await first_task
        finally:
            release.set()
            api.MAX_CONCURRENT_REQUESTS = original_limit
            api.MAX_QUEUED_REQUESTS = original_queue_limit
            api._active_requests = original_active
            api._queued_requests = original_queued

    asyncio.run(run_test())
