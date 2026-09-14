"""Golden retrieval evaluation: Hit@K and MRR per strategy.

    python -m app.retrieval.evaluation

Loads tests/gold_queries.json (queries + expected source files), runs every
retrieval strategy, and reports:

    Hit@K  — did ANY relevant source appear in the top K results?
    MRR    — 1 / (rank of the FIRST relevant document), averaged.

These are intentionally simple, honest metrics. The point is not to
manufacture impressive numbers but to see what each technique actually
improves (or fails to improve) on THIS corpus.

A retrieval "hit" is at the SOURCE level: any chunk from a relevant file
counts, because the gold set is defined per file, not per chunk.
"""
import json
import time

from app.config import TOP_K
from app.logging_config import get_logger, setup_logging
from app.paths import GOLD_QUERIES_PATH
from app.retrieval.engine import RetrievalEngine
from app.retrieval.models import STRATEGIES, RetrievalResult

logger = get_logger(__name__)


def hit_at_k(result: RetrievalResult, relevant: set[str], k: int) -> bool:
    """True if any of the top-k retrieved documents comes from a relevant
    source file (matching on the source path, not the chunk)."""
    retrieved_sources = {doc.source for doc in result.documents[:k]}
    return bool(retrieved_sources & relevant)


def reciprocal_rank(result: RetrievalResult, relevant: set[str]) -> float:
    """1 / rank of the first relevant document; 0.0 if none appears."""
    for doc in result.documents:
        if doc.source in relevant:
            return 1.0 / doc.rank
    return 0.0


def load_gold_queries(path=GOLD_QUERIES_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["queries"]


def evaluate(engine: RetrievalEngine, gold: list[dict],
             top_k: int = TOP_K, k_for_hit: int = 5,
             strategies: tuple = STRATEGIES) -> dict:
    """Run every strategy over the gold set. Returns per-strategy metrics."""
    metrics: dict[str, dict] = {}
    for strategy in strategies:
        hits = 0
        rr_sum = 0.0
        total_latency_ms = 0.0
        per_query = []
        for item in gold:
            relevant = set(item["relevant_sources"])
            started = time.perf_counter()
            result = engine.retrieve(item["query"], strategy=strategy, top_k=top_k)
            total_latency_ms += (time.perf_counter() - started) * 1000

            hit = hit_at_k(result, relevant, k=k_for_hit)
            rr = reciprocal_rank(result, relevant)
            hits += hit
            rr_sum += rr
            per_query.append({
                "query": item["query"],
                "hit": hit,
                "rr": rr,
                "n_results": len(result.documents),
                "fallback": result.diagnostics.get("llm_fallback_used", False),
            })
        n = len(gold)
        metrics[strategy] = {
            "hit_at_k": hits / n,
            "mrr": rr_sum / n,
            "avg_latency_ms": round(total_latency_ms / n, 1),
            "avg_results": round(
                sum(q["n_results"] for q in per_query) / n, 1
            ),
            "n_fallbacks": sum(1 for q in per_query if q["fallback"]),
            "per_query": per_query,
        }
    return metrics


def print_report(metrics: dict, top_k: int, k_for_hit: int) -> None:
    print("\n" + "=" * 72)
    print(f"GOLD SET EVALUATION  (top_k={top_k}, Hit@{k_for_hit}, {len(metrics)} strategies)")
    print("=" * 72)
    header = f"{'strategy':<12} {'Hit@' + str(k_for_hit):>7} {'MRR':>7} {'avg_ms':>9} {'fallbacks':>10}"
    print(header)
    print("-" * len(header))
    for strategy, m in metrics.items():
        print(
            f"{strategy:<12} {m['hit_at_k']:>7.2f} {m['mrr']:>7.3f} "
            f"{m['avg_latency_ms']:>9.1f} {m['n_fallbacks']:>10}"
        )
    print("-" * len(header))
    print("\nReading the table:")
    print("  Hit@K — fraction of queries where at least one relevant source")
    print("           appeared in the top K (recall-oriented).")
    print("  MRR   — mean reciprocal rank (how HIGH the first relevant doc")
    print("           ranks; precision-at-the-top oriented).")
    print("  fallbacks — multi-query queries that fell back to the original")
    print("           query (LLM unavailable).")


def main() -> int:
    setup_logging()
    gold = load_gold_queries()
    engine = RetrievalEngine()
    print(f"Evaluating {len(gold)} gold queries…")
    metrics = evaluate(engine, gold)
    print_report(metrics, top_k=TOP_K, k_for_hit=5)

    # Per-query detail for strategies that missed — the interesting part.
    print("\nMISSES (queries where a strategy found nothing relevant):")
    for strategy, m in metrics.items():
        misses = [q for q in m["per_query"] if not q["hit"]]
        if misses:
            print(f"\n  {strategy}:")
            for q in misses:
                print(f"    - {q['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
