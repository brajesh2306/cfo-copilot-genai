# Technical Decision Log
## CFO Copilot — Engineering Decisions, Experiments and Lessons

**Project:** CFO Copilot on a Budget
**Document:** Technical Decision Log
**Purpose:** Record important engineering decisions, their rationale, trade-offs, implementation evidence and remaining limitations.

---

## 1. Architecture and Data Decisions

### D-001 — Source-Preserving Relational Ingestion

**Decision:** Preserve each original statement line, unit, filing ID and row ID. Assign canonical labels only through explicitly defined aliases.

**Reason:** Financial calculations must remain traceable to their original evidence. Unknown labels must not be silently reinterpreted.

**Trade-off:** Some values remain unavailable until their aliases are reviewed and mapped.

**Implementation:** Financial normalization, canonical aliases and source-row traceability are covered by the financial service and regression tests.

**Status:** Implemented; continue expanding alias coverage as new source data is introduced.

### D-002 — Deterministic Financial KPI Calculations

**Decision:** Perform financial calculations in Python/domain services rather than relying on the language model.

**Reason:**
- Financial arithmetic must be reproducible.
- Missing inputs must not be guessed.
- Results must be traceable to source records.
- The LLM should explain evidence, not become the authority for financial calculations.

**Trade-off:** The system may withhold an answer when required source values are unavailable.

**Implementation:** Deterministic KPI processing, unit normalization, canonical aliases and source-row references are covered by financial tests.

**Status:** Implemented.

### D-003 — Explicit Filing Amendment Policy

**Decision:** Prefer the latest applicable filing record for a company, fiscal period and canonical line item, while retaining the selected filing and source row identifiers.

**Reason:** Amended filings can change historical financial values. The system must apply a reproducible conflict-resolution policy.

**Trade-off:** A later filing should not automatically be treated as comparable if its period, units or accounting definition differ.

**Implementation evidence:**
- NWI FY2024 Q3 amendment regression coverage.
- Amended gross-margin handling.
- Year-over-year amended-data traceability.
- Source-row references for selected values.

**Status:** Implemented with regression coverage. Comparability and filing-selection edge cases should continue to be reviewed.

### D-004 — Separate Structured Financial Retrieval from Document RAG

**Decision:** Maintain separate paths for structured financial questions and unstructured filing-related questions.

**Reason:** A financial KPI lookup should not depend on semantic similarity alone. Conversely, a filing explanation requires relevant document context.

**Expected routing:**

| Question type | Processing path |
|---|---|
| KPI or financial value | Structured financial tools |
| Filing explanation | RAG retrieval |
| Mixed question | Structured tools and RAG |
| Missing or unsupported information | Withhold unsupported claims |
| Security-sensitive request | Security policy |

**Trade-off:** More explicit routing and validation are required, but the architecture becomes easier to test and reason about.

**Status:** Implemented through agent routing, financial tools and retrieval services; evaluation artifacts cover routing behavior.

### D-005 — Streamlit UI with Separate FastAPI Layer

**Decision:** Use Streamlit for the demonstration interface and FastAPI as a separate API layer.

**Reason:**
- Streamlit accelerates development of the demonstration interface.
- FastAPI provides typed, versioned endpoints.
- Presentation remains separate from business logic.
- API behavior can be tested independently.

**Trade-off:** The application has separate UI and API services to configure and operate.

**Status:** Implemented.

---

## 2. Model and Agent Decisions

### D-006 — Local Open-Weight Model Inference

**Decision:** Use Ollama to serve a locally hosted open-weight model rather than depending on hosted LLM inference.

**Reason:** The assignment requires a private, self-hosted inference approach with controlled infrastructure and reproducible experiments.

**Models evaluated in project artifacts:**
- Qwen 2.5 1.5B.
- Llama 3.2 1B.

**Trade-off:** Small models reduce resource requirements but may be less reliable at complex tool selection and structured reasoning.

**Implementation:** Ollama connectivity and local model configuration are part of the application setup.

**Status:** Implemented; model quality and performance comparisons are documented separately in benchmark artifacts.

### D-007 — Google ADK for Agent Orchestration

**Decision:** Use Google ADK to coordinate the root agent, specialized tools and question-routing workflow.

**Reason:** Agent orchestration should be separate from financial calculations, SQL access and document retrieval.

**Design principles:**
- Keep business rules in domain services.
- Expose controlled tools to the agent.
- Use structured financial tools for KPI questions.
- Use document retrieval for filing-related questions.
- Verify outputs against available evidence.
- Avoid unnecessary model calls.

**Evaluation evidence:** The project includes trajectory evaluation scripts that record tool calls, tool responses, final responses, route outcomes and execution latency.

**Important metric distinction:** Recorded LLM response events are not necessarily equivalent to actual provider API calls.

**Status:** Implemented with automated evaluation artifacts.

### D-008 — Deterministic Security Handling

**Decision:** Apply security checks before untrusted input can influence sensitive agent actions.

**Reason:** User prompts and retrieved documents may contain instructions intended to manipulate the model, disclose information or bypass tool restrictions.

**Design principles:**
- Treat user-provided and retrieved content as untrusted.
- Do not expose internal prompts or secrets.
- Do not let malicious instructions replace deterministic financial results.
- Restrict sensitive tool behavior.
- Prefer safe refusal over unsupported disclosure.

**Implementation evidence:** Security regression tests exercise prompt-injection scenarios and check that malicious content does not replace supported financial KPI processing.

**Status:** Implemented with security evaluation coverage. Production authorization and tenant-isolation controls still require independent verification.

### D-009 — Streaming Responses and Bounded Request Handling

**Decision:** Provide SSE streaming and bounded request handling through the API.

**Reason:** Streaming improves response delivery, while queue and concurrency limits protect the service from unbounded request accumulation.

**Design principles:**
- Validate incoming requests.
- Associate requests with identifiers.
- Bound concurrent work and queued requests.
- Return an overload response when capacity is exceeded.
- Provide retry guidance where appropriate.
- Avoid caching streaming responses.

**Implementation evidence:** Chat and streaming tests cover request IDs, queue behavior, overload responses, retry headers and SSE events.

**Status:** Implemented with automated tests.

---

## 3. KV Cache Diagnosis

### D-010 — Diagnose Prefix Cache Behavior Before Changing Configuration

**Decision:** Document the observed cache behavior before introducing speculative prompt or cache optimizations.

**Evidence from the supplied log analysis:**
- 220 requests were examined.
- 219 requests reported 16 cached tokens.
- One request reported zero cached tokens.
- Dynamic timestamp and request ID values appeared early in the system instructions.

**Hypothesis:** Dynamic content in the shared prompt prefix may reduce prefix reuse.

**Trade-off:** Reordering dynamic information may improve prefix reuse, but this must be validated against actual runtime behavior.

**Status:** Diagnosis documented in `CACHE_DIAGNOSIS.md`. Controlled KV-cache benchmarking remains necessary.

---

## 4. Experiments, Failures and Redesign Lessons

### Experiment E-001 — Small Model Tool-Routing Reliability

**Observation:** Small local models can execute simple requests but may be unreliable when selecting tools for structured financial questions.

**Engineering response:** Strengthen explicit routing rules and keep common financial calculations deterministic.

**Lesson:** Financial correctness should not depend on the model correctly performing arithmetic or selecting a tool for every simple KPI question.

### Experiment E-002 — Amended Filing Regression

**Observation:** An amended filing can change the financial value selected for a historical period.

**Engineering response:** Apply a defined filing-selection policy and add regression coverage for amended NWI data.

**Lesson:** A financial result must retain the identity of the source records used to calculate it.

### Experiment E-003 — Missing Financial Inputs

**Observation:** A calculation may be impossible when one or more required inputs are missing.

**Engineering response:** Return an unavailable or withheld result instead of generating a guessed number.

**Lesson:** An explicit missing-data response is safer than a plausible but unsupported financial answer.

### Experiment E-004 — Prompt-Injection Handling

**Observation:** Untrusted instructions can attempt to change agent behavior or obtain information outside the intended task.

**Engineering response:** Add deterministic security checks and regression cases.

**Lesson:** Prompt instructions alone should not be treated as the application's security boundary.

### Experiment E-005 — Retrieval Evaluation

**Observation:** A retrieval system can return relevant-looking documents without necessarily retrieving sufficient evidence to answer a question correctly.

**Engineering response:** Evaluate retrieval separately from answer correctness and refusal behavior.

**Lesson:** Retrieval relevance, evidence sufficiency and final-answer correctness are different evaluation dimensions.

---

## 5. Retrieval Evaluation Record

The project benchmark artifacts report the following retrieval configuration:

| Property | Recorded value |
|---|---|
| Document corpus | 77 documents |
| Document chunks | 152 |
| Embedding dimensions | 384 |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Vector index | FAISS IndexFlatIP |
| Evaluation cases loaded | 21 |
| Cases scored | 18 |
| Cases excluded from ordinary retrieval scoring | 3 |
| Recall@5 | 55.56% |
| MRR@5 | 0.3833 |

The three excluded cases (`dev-19`, `dev-20`, `dev-21`) require refusal or security-behavior evaluation rather than ordinary company-period retrieval scoring.

### Evaluation Limitations

- Company, fiscal year and fiscal quarter metadata are used as a relevance proxy.
- Recall@5 does not independently establish financial answer correctness.
- Retrieval latency is not end-to-end API latency.
- Security and refusal behavior require separate evaluation.

**Metric reconciliation:** The current `evals/retrieval_results.json` is the selected final retrieval evaluation artifact:

- Mean retrieval latency: 9.99 ms.
- P95 retrieval latency: 13.8 ms.
- An earlier evaluation artifact, `evals/retrieval_results_previous.json`, records 11.59 ms mean and 16.02 ms P95.

Both runs report the same corpus, 18 scored cases, Recall@5 of 55.56% and MRR@5 of 0.3833. The current result is used in the final benchmark summary; the earlier result is retained as historical evidence. These are retrieval-only timings, not end-to-end inference latency.

---

## 6. Performance and Observability Decisions

### D-011 — Separate Measured Results from Performance Targets

**Decision:** Never present proposed performance targets as measured benchmark results.

**Reason:** Hardware, concurrency, prompt length, model selection and runtime configuration affect inference performance.

**Metrics to measure:**
- Time to First Token (TTFT).
- Tokens per second.
- Queue depth.
- Error rate.
- Cache hit rate.
- GPU and system memory consumption.
- KV-cache memory and behavior.
- End-to-end request latency.

**Status:** Measurement requirements documented. Existing benchmark artifacts include retrieval and API timing, but the complete KV-cache experiment and inference observability measurements must be verified separately.

### D-012 — Controlled KV-Cache Benchmarking

**Decision:** Compare the required cache configurations under controlled concurrency rather than assuming that a configured cache is performing effectively.

**Required experiment dimensions:**
- Three KV-cache configurations/levels.
- Concurrency: 1, 4 and 16 users.
- TTFT.
- Tokens per second.
- Cache hit rate.
- Memory consumption.
- Response quality and stability.

**Status:** Pending controlled measurements. No unmeasured cache improvements are claimed.

---

## 7. Known Limitations and Remaining Verification

The following items must be verified before production-readiness claims are made:

1. Complete three-level KV-cache comparison on the target runtime.
2. Actual TTFT, tokens-per-second and KV-cache memory measurements.
3. Tenant authorization and isolation across database, sessions, retrieval and cache.
4. Read-only database role enforcement for agent-facing SQL access.
5. Reproducible performance tests under the required concurrency levels.
6. Consistent model version, prompt hash and retrieval snapshot logging.
7. Final reconciliation of retrieval latency figures.
8. Confirmation that secrets are supplied through environment configuration and are not committed.

These are verification and benchmarking requirements; they should not be confused with already implemented and tested application functionality.

---

## 8. Main Implementation Files

| File or directory | Responsibility |
|---|---|
| `app/api.py` | API routes and request handling |
| `app/main.py` | Application startup |
| `app/agents/` | Agent orchestration and tool integration |
| `app/services/financials.py` | Financial calculations and source references |
| `app/services/retrieval.py` | Document processing and semantic retrieval |
| `migrations/001_initial.sql` | Initial relational database schema |
| `tests/test_financials.py` | Financial calculation and amendment tests |
| `tests/test_chat.py` | API and chat behavior tests |
| `tests/test_security.py` | Security regression tests |
| `tests/test_streaming.py` | Streaming response tests |
| `evals/` | Retrieval and agent evaluation artifacts |
| `benchmarks/` | Performance benchmark artifacts |
| `CACHE_DIAGNOSIS.md` | Prefix-cache diagnosis |
| `BENCHMARK_REPORT.md` | Benchmark summary |

---

## 9. Final Engineering Lessons

1. Financial arithmetic belongs in deterministic domain services, not free-form model generation.
2. Every financial answer should be traceable to source records.
3. Filing amendments require an explicit and testable conflict policy.
4. Structured financial retrieval and unstructured document retrieval should remain separate.
5. Agent tools should be controlled and independently testable.
6. Security requires enforcement outside the language model's instructions.
7. Retrieval quality must be evaluated separately from final-answer quality.
8. Performance claims must be backed by reproducible measurements.
9. Small local models require explicit evaluation of routing and tool-use reliability.
10. Production readiness requires verification of tenant isolation, credentials, observability and failure handling.

---

**Document status:** Engineering decision record prepared for technical review.

**Evidence policy:** Implementation claims, test evidence, benchmark measurements, hypotheses and remaining verification tasks are intentionally distinguished. No estimated or unmeasured performance value is presented as an experimental result.
