# CFO Copilot - Assignment Implementation

A local financial assistant using MySQL 8.0, FastAPI, Streamlit, deterministic KPI calculations, and FAISS-based semantic retrieval. The supplied financial data is fictional.

## Quick Start

Run from the project root:

    docker compose up --build

Open:
- Streamlit UI: http://localhost:8501
- API health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

Click Initialize / ingest data in the Streamlit sidebar to load the Candidate Pack and Drop 2.

Stop containers with docker compose down. Avoid docker compose down -v unless you intend to delete the database volume.

## Implemented Features

- MySQL-backed data ingestion and deterministic KPI calculations.
- Unit normalization for USD, USD_thousands, and USD_millions.
- Source-row traceability for calculated KPIs.
- Candidate Pack and Drop 2 document loading.
- FAISS semantic retrieval using sentence-transformers/all-MiniLM-L6-v2.
- Company, fiscal year, and fiscal quarter retrieval filters.
- FastAPI health, ingestion, companies, KPI, and chat endpoints.
- Chat responses with citation metadata and confidence fields.
- Low-confidence handling that withholds numeric answers when required KPI inputs are missing.
- Regression tests for the NWI FY2024 Q3 amendment and ZLG Drop 2 data.

## Amendment Policy

The financial data layer prioritizes the latest filing date for a canonical line item within a company and fiscal period. Source row IDs are retained for traceability. Tests cover the NWI FY2024 Q3 amendment, amended gross margin, and year-over-year revenue growth using amended revenue.

## Verification

Run tests with:

    docker compose exec api pytest -q

The last recorded check reported 11 passing tests. Re-run after changes to verify the current state.

## Pending Work

Google ADK orchestration, local generative model serving, SSE streaming, tenant authorization, comprehensive evaluation suites, load testing, model comparisons, and measured latency/GPU/KV-cache benchmarks are not verified as implemented.

The benchmarks and evals directories are currently empty. Do not report performance targets as measured results.

## Security

Example credentials are for local development only. Never commit real credentials; change example secrets before shared deployment.
