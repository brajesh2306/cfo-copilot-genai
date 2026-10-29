
import csv
import re
import json
import time
import statistics
from pathlib import Path

from app.services.retrieval import retrieve, corpus_stats

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "app" / "data" / "puzzle4_data" / "dev_questions.csv"
OUTPUT = ROOT / "evals" / "retrieval_results.json"


def parse_hint(hint):
    """Parse company and fiscal period, including optional MD&A suffix."""
    match = re.search(
        r"^\s*([A-Z]{3})\s+FY(\d{4})\s+Q([1-4])"
        r"(?:\s+MD&A)?\s*$",
        hint or "",
        re.IGNORECASE,
    )
    if not match:
        return None

    return {
        "company_id": match.group(1).upper(),
        "fiscal_year": int(match.group(2)),
        "fiscal_quarter": int(match.group(3)),
    }


def main():
    with INPUT.open("r", encoding="utf-8-sig", newline="") as file:
        cases = list(csv.DictReader(file))

    results = []
    latencies = []
    skipped_details = []

    stats = corpus_stats()

    for case in cases:
        hint = case.get("expected_source_hint", "")
        expected = parse_hint(hint)

        # Keep every case in the report, even if it cannot be scored.
        if expected is None:
            results.append({
                "case_id": case.get("id"),
                "question": case.get("question"),
                "expected_source_hint": hint,
                "expected_route": case.get("expected_route"),
                "status": "not_scored",
                "reason": (
                    "No parseable company-period hint; "
                    "review refusal, security, or other expected behavior separately."
                ),
            })
            skipped_details.append(case.get("id"))
            continue

        start = time.perf_counter()
        documents = retrieve(case["question"], top_k=5)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        rank = None
        for position, doc in enumerate(documents, start=1):
            try:
                year = int(float(doc.get("fiscal_year", "")))
                quarter = int(float(doc.get("fiscal_quarter", "")))
            except (TypeError, ValueError):
                continue

            if (
                doc.get("company_id") == expected["company_id"]
                and year == expected["fiscal_year"]
                and quarter == expected["fiscal_quarter"]
            ):
                rank = position
                break

        results.append({
            "case_id": case.get("id"),
            "question": case.get("question"),
            "expected_source_hint": hint,
            "expected_route": case.get("expected_route"),
            "expected": expected,
            "status": "scored",
            "retrieved_doc_ids": [doc["doc_id"] for doc in documents],
            "relevant_rank": rank,
            "recall_at_5": int(rank is not None),
            "reciprocal_rank": 1 / rank if rank else 0,
            "latency_ms": round(elapsed_ms, 2),
        })

    scored = [item for item in results if item["status"] == "scored"]
    count = len(scored)

    summary = {
        "evaluation": "unfiltered company-period retrieval proxy",
        "definition": (
            "A hit means at least one top-5 retrieved document matches "
            "the expected company, fiscal year, and fiscal quarter. "
            "This is only a metadata-based relevance proxy, not proof "
            "that the answer is correct or supported by the document."
        ),
        "corpus_stats": stats,
        "cases_loaded": len(cases),
        "cases_reported": len(results),
        "cases_scored": count,
        "cases_not_scored": len(skipped_details),
        "not_scored_case_ids": skipped_details,
        "recall_at_5": (
            sum(item["recall_at_5"] for item in scored) / count
            if count else None
        ),
        "mrr_at_5": (
            sum(item["reciprocal_rank"] for item in scored) / count
            if count else None
        ),
        "mean_latency_ms": (
            round(statistics.mean(latencies), 2) if latencies else None
        ),
        "p95_latency_ms": (
            round(
                sorted(latencies)[min(
                    len(latencies) - 1,
                    int(0.95 * len(latencies))
                )],
                2,
            )
            if latencies else None
        ),
        "results": results,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(
        {key: value for key, value in summary.items() if key != "results"},
        indent=2,
    ))
    print(f"\nDetailed results: {OUTPUT}")


if __name__ == "__main__":
    main()
