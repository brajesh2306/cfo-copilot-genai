# Technical Decision Log

## D-001 — Start with source-preserving relational ingestion
- **Decision:** Preserve each raw statement line, original unit, filing ID and row ID; add a canonical label only when an explicit alias exists.
- **Reason:** KPI values must be traceable to original evidence and unknown labels must not be silently reinterpreted.
- **Trade-off:** Some values will remain unavailable until aliases are reviewed.
- **Status:** Initial implementation; coverage and financial correctness tests still required.

## D-002 — KPI calculations are deterministic
- **Decision:** Compute KPI formulas in Python/SQL, not in the LLM.
- **Reason:** The assignment explicitly requires calculations outside the model and missing values must not be guessed.
- **Trade-off:** The model can explain results but cannot fill missing source values.

## D-003 — Filing amendment policy
- **Decision:** Prefer the latest filed record for a given company/period/canonical line item, with amended filing status and source ID retained. Any KPI affected by amendment must expose the selected source rows.
- **Reason:** The source pack asks for an explicit, reproducible conflict policy.
- **Open issue:** Need tests comparing original vs amended NWI FY2024 Q3 answers and review whether all source lines are comparable.

## D-004 — Prefix cache diagnosis before changing code
- **Decision:** Record the log-based diagnosis in `CACHE_DIAGNOSIS.md` before prompt/cache changes.
- **Evidence:** 220 requests; 219 have 16 cached tokens, one has 0; dynamic timestamp/request ID occur inside early system instructions.
- **Status:** Hypothesis documented; controlled benchmark remains required.

## D-005 — UI choice
- **Decision:** Streamlit for the demonstration UI; FastAPI is kept as a separate typed API layer.
- **Reason:** Streamlit is permitted by the user for UI and keeps presentation separate from domain services.

## Experiments and failures

No model latency, KV-cache, retrieval-quality or GPU-memory measurements have been claimed yet. These must be populated from actual runs. Do not substitute estimated numbers for measurements.
