# Performance Benchmark Report

Date: 2026-10-30
Environment: Windows 11, Intel i7-11370H, NVIDIA RTX 3050 4GB, 7.8GB RAM, Python 3.10.

## 1. Retrieval benchmark

- Corpus documents: 77
- Chunks: 152
- Embedding model: sentence-transformers/all-MiniLM-L6-v2
- Index: FAISS IndexFlatIP
- Evaluation cases loaded: 21
- Scored: 18
- Not scored: 3 (dev-19, dev-20, dev-21)
- Recall@5: 55.56%
- MRR@5: 0.3833
- Mean latency: 9.99 ms
- P95 latency: 13.8 ms

Recall@5 is a metadata-based company/period relevance proxy, not proof of answer correctness.

## 2. API benchmark

10 sequential requests per endpoint; 40 requests total.

| Endpoint | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|
| Health | 8.01 | 2.91 | 52.54 |
| Companies | 42.59 | 4.25 | 386.52 |
| KPIs | 78.46 | 56.95 | 304.68 |
| Chat | 1541.65 | 65.97 | 14810.32 |

All four endpoints returned OK. The chat endpoint showed substantial latency variability. These are local sequential measurements, not a production load test.

## 3. Agent evaluation

Qwen 2.5 1.5B:
- Development trajectories: 41/41 executed successfully.
- Route checks: 21/21 matched (100%).
- Average LLM response events: 1.98.
- Security adversarial cases: 20; zero tools invoked.
- Held-out security cases: 5/5 safely blocked; zero tools invoked.
- Average response events on held-out cases: 1.0.

Llama 3.2 1B comparison:
- 41/41 executed.
- Route accuracy: 17/21 (80.95%).
- Average response events: 2.17.
- Some security and routing weaknesses observed.

Response events are not equivalent to provider API calls.

## 4. Model runtime

- Model: Qwen 2.5 1.5B
- Quantization: Q4_K_M
- Model size reported by Ollama: 1.2 GB
- Processor placement: 100% GPU
- Active context: 4096 tokens
- Model metadata maximum context: 32768 tokens

## 5. Limitations

- request_metrics currently contains zero records.
- TTFT and tokens/second have not been measured.
- KV-cache hit rate and actual KV-cache memory consumption have not been measured.
- No controlled concurrency/load benchmark has been performed.
- Retrieval relevance proxy does not establish answer correctness.
- API latency results are local observations and are not production SLAs.

## 6. Conclusion

Retrieval latency is low in the measured local evaluation. The API chat endpoint has high latency variability and needs profiling. Qwen 2.5 1.5B performed better than Llama 3.2 1B on the recorded trajectory routing and security evaluations. Further work is required for token-level performance, KV-cache instrumentation, and concurrent load testing.

## Retrieval Benchmark — Historical Run Reconciliation

The selected final retrieval result is from `evals/retrieval_results.json`:
- Mean latency: 9.99 ms
- P95 latency: 13.8 ms
- Recall@5: 55.56%
- MRR@5: 0.3833

The earlier run in `evals/retrieval_results_previous.json` recorded 11.59 ms mean and 16.02 ms P95, with the same Recall@5 and MRR@5. Both result files are retained for reproducibility. The current result is used as the final reported retrieval benchmark.

These timings measure retrieval only, not end-to-end LLM response latency.
