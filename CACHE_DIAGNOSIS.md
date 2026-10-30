# KV-Cache Diagnosis

## Runtime observations

Ollama reported:
- Model: Qwen 2.5 1.5B
- Quantization: Q4_K_M
- Model size: 1.2 GB
- GPU placement: 100%
- Active context: 4096 tokens
- Model metadata context limit: 32768 tokens

## KV-cache status

The current request_metrics table has zero rows. Therefore TTFT, tokens/second, cache-hit rate, queue depth and actual KV-cache memory usage have not been empirically measured.

The active context of 4096 is a runtime setting, not a measurement of KV-cache occupancy.

## Memory estimate (illustrative only)

For a hypothetical FP16 KV cache, memory is approximately:

layers x 2 (key/value) x KV heads x head dimension x context tokens x 2 bytes.

This estimate requires confirmed architecture and cache datatype settings. It is not reported as measured GPU memory. Quantized model weights do not imply that the KV cache is also quantized.

## Diagnosis

1. Model weights are fully GPU-resident according to `ollama ps`.
2. The active context is 4096 tokens, below the model metadata maximum of 32768.
3. No KV-cache hit-rate or occupancy instrumentation is currently populated.
4. The API chat endpoint has high latency variability; profiling is required before attributing it to KV-cache pressure.
5. Do not claim a KV-cache optimization or measured cache hit rate without instrumentation.

## Recommended next measurements

- Record TTFT and generation tokens per second from the Ollama runtime.
- Record prompt and generated token counts.
- Record GPU memory before and during inference.
- Compare controlled context lengths (for example 2048 and 4096).
- Run repeated warm and cold requests separately.
- Populate request_metrics with real observations.
