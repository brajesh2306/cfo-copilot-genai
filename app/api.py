from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.services.financials import database_initialized, initialize_db, ingest_all, list_companies, compute_kpis
from app.services.retrieval import retrieve

app = FastAPI(title='CFO Copilot API', version='v1')
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
    question: str = Field(min_length=3, max_length=2000)


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
