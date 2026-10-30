import asyncio
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from uuid import uuid4
from pydantic import BaseModel, Field
from app.services.financials import database_initialized, initialize_db, ingest_all, list_companies, compute_kpis
from app.services.retrieval import retrieve
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agents.cfo_agent import root_agent

ADK_APP_NAME = "cfo_copilot"
ADK_USER_ID = "local_user"
adk_session_service = InMemorySessionService()
adk_runner = Runner(
    agent=root_agent,
    app_name=ADK_APP_NAME,
    session_service=adk_session_service,
)


app = FastAPI(title='CFO Copilot API', version='v1')

logger = logging.getLogger("cfo_copilot.api")


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "REQUEST_VALIDATION_FAILED",
                "message": "Request input is invalid.",
                "errors": exc.errors(),
            },
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled API error request_id=%s", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            },
            "request_id": request_id,
        },
    )


MAX_CONCURRENT_REQUESTS = max(
    1, int(os.getenv("MAX_CONCURRENT_REQUESTS", "16"))
)
MAX_QUEUED_REQUESTS = max(
    0, int(os.getenv("MAX_QUEUED_REQUESTS", "32"))
)
QUEUE_WAIT_TIMEOUT_SECONDS = max(
    0.01, float(os.getenv("QUEUE_WAIT_TIMEOUT_SECONDS", "1"))
)

_active_requests = 0
_queued_requests = 0
_request_condition = asyncio.Condition()


def service_busy_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        headers={
            "Retry-After": "1",
            "X-Request-ID": request_id,
        },
        content={
            "detail": {
                "code": "SERVICE_BUSY",
                "message": "Server is busy. Retry the request shortly.",
            },
            "request_id": request_id,
        },
    )


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    global _active_requests, _queued_requests

    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id

    async with _request_condition:
        if _active_requests >= MAX_CONCURRENT_REQUESTS:
            if _queued_requests >= MAX_QUEUED_REQUESTS:
                return service_busy_response(request_id)

            _queued_requests += 1
            try:
                await asyncio.wait_for(
                    _request_condition.wait_for(
                        lambda: _active_requests < MAX_CONCURRENT_REQUESTS
                    ),
                    timeout=QUEUE_WAIT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                _queued_requests -= 1
                _request_condition.notify_all()
                return service_busy_response(request_id)
            except BaseException:
                _queued_requests -= 1
                _request_condition.notify_all()
                raise
            else:
                _queued_requests -= 1

        _active_requests += 1

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        async with _request_condition:
            _active_requests -= 1
            _request_condition.notify_all()

class IngestResponse(BaseModel): status: str
class KPIRequest(BaseModel): company_id: str = Field(min_length=1); fiscal_year: int; fiscal_quarter: int = Field(ge=1, le=4)

@app.get('/api/v1/health')
def health(): return {'status':'ok','database_initialized':database_initialized()}

@app.post('/api/v1/ingest', response_model=IngestResponse)
def ingest():
    try: ingest_all(); return {'status':'ingested'}
    except Exception as e: raise HTTPException(status_code=500, detail={'code':'INGEST_FAILED','message':str(e)})

@app.get('/api/v1/companies')
def companies():
    try: return list_companies().to_dict(orient='records')
    except Exception as e: raise HTTPException(status_code=503, detail={'code':'DATABASE_UNAVAILABLE','message':str(e)})

@app.post('/api/v1/kpis')
def kpis(req: KPIRequest):
    known={r['company_id'] for r in list_companies().to_dict(orient='records')}
    if req.company_id not in known: raise HTTPException(status_code=404, detail={'code':'COMPANY_NOT_FOUND'})
    return {'company_id':req.company_id,'fiscal_year':req.fiscal_year,'fiscal_quarter':req.fiscal_quarter,'kpis':compute_kpis(req.company_id,req.fiscal_year,req.fiscal_quarter)}


class ChatRequest(BaseModel):
    company_id: str = Field(min_length=1)
    fiscal_year: int
    fiscal_quarter: int = Field(ge=1, le=4)
    question: str = Field(min_length=1, max_length=2000)


@app.post("/api/v1/search")
def search_documents(req: ChatRequest):
    """Retrieve filing evidence directly without KPI-name matching."""
    known = {
        r["company_id"]
        for r in list_companies().to_dict(orient="records")
    }
    if req.company_id not in known:
        raise HTTPException(
            status_code=404,
            detail={"code": "COMPANY_NOT_FOUND"},
        )

    try:
        evidence = retrieve(
            req.question,
            company_id=req.company_id,
            fiscal_year=req.fiscal_year,
            fiscal_quarter=req.fiscal_quarter,
            top_k=5,
        )
    except Exception:
        logger.exception("Document retrieval failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "RETRIEVAL_UNAVAILABLE"},
        )

    citations = [
        {
            "doc_id": item["doc_id"],
            "title": item["title"],
            "filed_date": item["filed_date"],
            "similarity": round(item["similarity"], 4),
            "excerpt": item["text"][:1200],
        }
        for item in evidence
    ]

    return {
        "company_id": req.company_id,
        "fiscal_year": req.fiscal_year,
        "fiscal_quarter": req.fiscal_quarter,
        "answer": (
            f"Retrieved {len(citations)} relevant evidence chunks."
            if citations else
            "No matching filing evidence was found for this company and period."
        ),
        "confidence": "medium" if citations else "low",
        "confidence_basis": (
            "Results are ranked by FAISS semantic similarity and filtered "
            "to the selected company and fiscal period."
        ),
        "citations": citations,
    }


@app.post("/api/v1/assistant")
async def adk_assistant(req: ChatRequest):
    """Run the Google ADK CFO agent with the configured local Ollama model."""
    known = {
        r["company_id"]
        for r in list_companies().to_dict(orient="records")
    }
    if req.company_id not in known:
        raise HTTPException(
            status_code=404,
            detail={"code": "COMPANY_NOT_FOUND"},
        )

    # Deterministic retrieval for financial statement line-item questions.
    question_lower = req.question.lower()
    requested_items = []
    if any(term in question_lower for term in ("revenue", "revenues", "net sales", "total sales")):
        requested_items.append(("revenue", "Revenue"))
    if any(term in question_lower for term in ("gross profit", "gross margin")):
        requested_items.append(("gross_profit", "Gross profit"))

    if requested_items:
        from app.services.financials import source_values

        try:
            financial_rows = source_values(
                req.company_id, req.fiscal_year, req.fiscal_quarter
            )
            answer_lines = []
            citations = []

            for canonical, label in requested_items:
                matches = financial_rows[
                    (financial_rows["canonical_item"] == canonical)
                    & financial_rows["value_usd"].notna()
                ]
                if matches.empty:
                    answer_lines.append(f"{label}: Not available for this period.")
                    continue

                row = matches.iloc[0]
                value = float(row["value_usd"])
                row_id = str(row["row_id"])
                answer_lines.append(f"{label}: ${value:,.2f} USD")
                citations.append(row_id)

            return {
                "company_id": req.company_id,
                "fiscal_year": req.fiscal_year,
                "fiscal_quarter": req.fiscal_quarter,
                "answer": "\\n".join(answer_lines),
                "citations": citations,
                "confidence": "high" if citations else "low",
                "execution": "deterministic_financial_data",
            }
        except Exception:
            logger.exception("Deterministic financial line-item lookup failed")
            raise HTTPException(
                status_code=503,
                detail={"code": "FINANCIAL_DATA_UNAVAILABLE"},
            )

    session_id = str(uuid4())
    prompt = (
        f"Selected context: company_id={req.company_id}; "
        f"fiscal_year={req.fiscal_year}; "
        f"fiscal_quarter={req.fiscal_quarter}.\n"
        f"User question: {req.question}\n\n"
        "Use the available financial KPI and document retrieval tools. "
        "For numerical answers, rely on tool results. For filing questions, "
        "retrieve relevant evidence and cite document titles or IDs. "
        "If evidence is insufficient, say so. Do not invent figures or sources."
    )

    try:
        await adk_session_service.create_session(
            app_name=ADK_APP_NAME,
            user_id=ADK_USER_ID,
            session_id=session_id,
        )

        final_answer = ""
        async for event in adk_runner.run_async(
            user_id=ADK_USER_ID,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            ),
        ):
            if event.is_final_response() and event.content:
                parts = event.content.parts or []
                final_answer = "\n".join(
                    part.text for part in parts if getattr(part, "text", None)
                )

        if not final_answer.strip():
            raise RuntimeError("ADK returned no final text response.")

        return {
            "company_id": req.company_id,
            "fiscal_year": req.fiscal_year,
            "fiscal_quarter": req.fiscal_quarter,
            "answer": final_answer,
            "agent": root_agent.name,
            "model": os.getenv("CFO_MODEL", "ollama_chat/llama3.2:1b"),
            "execution": "google_adk_runner",
        }

    except Exception:
        logger.exception("ADK assistant execution failed")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ADK_EXECUTION_FAILED",
                "message": (
                    "The AI assistant could not complete the request. "
                    "Check API logs and Ollama connectivity."
                ),
            },
        )


@app.post("/api/v1/chat")
def chat(req: ChatRequest):
    known = {
        r["company_id"]
        for r in list_companies().to_dict(orient="records")
    }

    if req.company_id not in known:
        raise HTTPException(
            status_code=404,
            detail={"code": "COMPANY_NOT_FOUND"},
        )

    kpis = compute_kpis(
        req.company_id,
        req.fiscal_year,
        req.fiscal_quarter,
    )

    question = req.question.casefold()
    matched = [
        kpi for kpi in kpis
        if kpi["kpi_name"].casefold() in question
        or kpi["kpi_id"].replace("_", " ").casefold() in question
    ]

    try:
        evidence = retrieve(
            req.question,
            company_id=req.company_id,
            fiscal_year=req.fiscal_year,
            fiscal_quarter=req.fiscal_quarter,
            top_k=3,
        )
    except Exception:
        evidence = []

    citations = [
        {
            "doc_id": item["doc_id"],
            "title": item["title"],
            "filed_date": item["filed_date"],
            "similarity": round(item["similarity"], 3),
            "excerpt": item["text"][:500],
        }
        for item in evidence
    ]

    if len(matched) != 1:
        return {
            "company_id": req.company_id,
            "fiscal_year": req.fiscal_year,
            "fiscal_quarter": req.fiscal_quarter,
            "answer": (
                "I could not identify one specific KPI from the question. "
                "Please ask about a KPI by its displayed name."
            ),
            "confidence": "low",
            "confidence_basis": (
                "The question did not uniquely identify a supported KPI."
            ),
            "source_row_ids": [],
            "citations": citations,
        }

    kpi = matched[0]

    if kpi["value"] is None or kpi["confidence"] == "low":
        return {
            "company_id": req.company_id,
            "fiscal_year": req.fiscal_year,
            "fiscal_quarter": req.fiscal_quarter,
            "answer": (
                "The numeric answer is withheld because the evidence is insufficient."
            ),
            "value": None,
            "unit": kpi["unit"],
            "kpi_name": kpi["kpi_name"],
            "confidence": "low",
            "confidence_basis": kpi["confidence_basis"],
            "source_row_ids": kpi["source_row_ids"],
            "citations": citations,
        }

    return {
        "company_id": req.company_id,
        "fiscal_year": req.fiscal_year,
        "fiscal_quarter": req.fiscal_quarter,
        "answer": (
            f'{kpi["kpi_name"]}: {kpi["value"]:.2f} {kpi["unit"]}'
        ),
        "value": kpi["value"],
        "unit": kpi["unit"],
        "kpi_name": kpi["kpi_name"],
        "confidence": kpi["confidence"],
        "confidence_basis": kpi["confidence_basis"],
        "source_row_ids": kpi["source_row_ids"],
        "citations": citations,
    }


# Server-Sent Events endpoint. Streams the existing deterministic chat result;
# this is transport streaming, not token generation from an LLM.
@app.post("/api/v1/chat/stream")
def chat_stream(req: ChatRequest):
    import json
    from fastapi.responses import StreamingResponse

    result = chat(req)
    if not isinstance(result, dict):
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        elif hasattr(result, "dict"):
            result = result.dict()
        else:
            result = {"answer": str(result)}

    answer = str(result.get("answer", ""))
    chunk_size = 32

    def event_stream():
        for start in range(0, len(answer), chunk_size):
            payload = {"text": answer[start:start + chunk_size]}
            yield "event: token\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        yield "event: done\ndata: " + json.dumps(
            {"result": result}, ensure_ascii=False, default=str
        ) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
