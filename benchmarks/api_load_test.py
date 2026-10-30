"""Concurrent HTTP smoke/load test. Measures API latency, not model/KV-cache speed."""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def request_once(url, timeout):
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            response.read()
        error = None
    except Exception as exc:
        status = None
        error = type(exc).__name__ + ": " + str(exc)
    return {
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "status": status,
        "error": error,
    }


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((p / 100) * len(ordered) + 0.999999) - 1))
    return round(ordered[index], 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--output", default="benchmarks/api_load_results.json")
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(
            lambda _: request_once(args.url, args.timeout),
            range(args.requests),
        ))
    elapsed = time.perf_counter() - started

    latencies = [r["latency_ms"] for r in results]
    successes = sum(r["status"] is not None and 200 <= r["status"] < 300 for r in results)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(args.requests / elapsed, 3) if elapsed else None,
        "successful_responses": successes,
        "failed_responses": args.requests - successes,
        "mean_latency_ms": round(statistics.mean(latencies), 3) if latencies else None,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "max_latency_ms": round(max(latencies), 3) if latencies else None,
        "errors": [r["error"] for r in results if r["error"]][:20],
        "scope_note": "HTTP endpoint load measurement only; not a generative-model or KV-cache benchmark.",
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    if successes != args.requests:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
