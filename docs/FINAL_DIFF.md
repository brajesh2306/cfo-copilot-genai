# Final Diff and Implementation Notes

## 1. What Changed

- Added deterministic financial KPI calculations and source-row traceability.
- Added unit normalization for USD, USD_thousands, and USD_millions.
- Added FAISS semantic retrieval over the Candidate Pack and Drop 2 corpora.
- Added company, fiscal year, and fiscal quarter filters for document retrieval.
- Added chat response citations and confidence metadata.
- Added low-confidence handling that withholds numeric answers when required KPI inputs are missing.
- Added regression coverage for NWI FY2024 Q3 amendment behavior and ZLG Drop 2.

## 2. Main Files

- app/services/financials.py: financial calculations and source-row references.
- app/services/retrieval.py: document loading, chunking, embeddings, and FAISS retrieval.
- app/api.py: API endpoints and chat response handling.
- tests/test_financials.py: financial and amendment regression tests.
- tests/test_chat.py: chat behavior and error-handling tests.
- docs/ARCHITECTURE.md: architecture and performance targets.
- docs/DECISIONS.md: implementation decisions and rationale.
- docs/DATA_AUDIT.md: source-data audit.
- README.md: setup, implemented functionality, and pending work.

## 3. Amendment Policy

The financial data layer prioritizes the latest filing date for a canonical line item within a company and fiscal period. Source row IDs remain traceable. Regression tests check the NWI amended gross margin and year-over-year revenue growth.

## 4. Verification

The last recorded automated test run reported 11 passing tests. Re-run the test suite before submission to confirm the current state.

## 5. Known Gaps

- Basic company-period retrieval evaluation is implemented; comprehensive answer-quality, evidence-sufficiency, refusal, and security evaluation remains pending.
- The evals directory contains a retrieval evaluation script and generated JSON results; target-hardware benchmarking remains pending.
- Google ADK orchestration, local generative model serving, and SSE streaming are not verified as implemented.
- Tenant authorization, load testing, model comparisons, and target-GPU performance measurements remain unverified.
- Performance targets are not measured benchmark results.

## 6. Lessons and Redesign

- Keep financial arithmetic deterministic rather than relying on a language model to calculate figures.
- Preserve source-row IDs so answers can be traced to the underlying data.
- Treat amended filings explicitly and maintain regression tests for changed historical values.
- Separate financial KPI calculations from document retrieval.
- Add relevance and evidence-quality checks before treating retrieved documents as support for a numerical answer.
- Benchmark latency, memory, and concurrency on the actual target hardware before making performance claims.

## 7. Retrieval Evaluation

- Added `evals/evaluate_retrieval.py` to evaluate semantic retrieval against the development questions.
- Evaluation input: `app/data/puzzle4_data/dev_questions.csv`.
- Detailed output: `evals/retrieval_results.json`.
- Corpus measured: 77 documents, 152 chunks, 384-dimensional embeddings.
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
- Index: FAISS `IndexFlatIP`.
- Cases reported: 21.
- Cases scored for company-period retrieval: 18.
- Cases not scored by this metric: 3 (`dev-19`, `dev-20`, `dev-21`), because these cases require refusal or security-behavior validation rather than ordinary company-period retrieval scoring.
- Recall@5: 55.56%.
- MRR@5: 0.3833.
- Mean retrieval latency: 11.59 ms.
- P95 retrieval latency: 16.02 ms.

### Evaluation Limitations

- Recall@5 uses company, fiscal year, and fiscal quarter metadata as a relevance proxy; it does not verify answer correctness or evidence sufficiency.
- Refusal and security cases require separate behavioral tests.
- Latency figures measure retrieval execution in this evaluation run, not end-to-end API response time.
- Results are environment-specific and should be reproduced before making final performance claims.
