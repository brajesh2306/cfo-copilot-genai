.PHONY: up test ingest api
up:
	docker compose up --build
test:
	pytest -q
ingest:
	python -c "import sys;sys.path.insert(0,'app');from services.financials import ingest_all;ingest_all();print('ingestion complete')"
api:
	uvicorn app.api:app --reload
