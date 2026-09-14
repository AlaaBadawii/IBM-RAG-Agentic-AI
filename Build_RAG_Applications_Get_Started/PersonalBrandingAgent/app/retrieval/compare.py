"""Retrieval Comparison Playground — the main CLI of this milestone.

    python -m app.retrieval.compare "What evidence supports my backend engineering skills?"

Runs ONE question through all six strategies and prints them side-by-side,
then a summary, then deterministic explanations of WHY results differ
(no LLM needed for the explanations — they are computed from query/document
term overlap and per-strategy provenance).
"""
import argparse
import sys
from collections import Counter

from app.logging_config import setup_logging
from app.retrieval.bm25 import tokenize
from app.retrieval.engine import RetrievalEngine
from app.retrieval.models import STRATEGIES, RetrievalResult

STRATEGY_ORDER = ("vector", "metadata", "bm25", "multi_query", "hybrid", "reranked")

# Show the metadata strategy with a filter derived deterministically from the
# question's keywords (NOT an LLM) — so the playground always has something
# to compare. Documented as a heuristic, not "intelligent filtering".
# Order matters: more specific hints are checked first so they combine
# (e.g. "verified evidence" -> category + evidence_state, not just category).
_FILTER_HINTS = {
    "verified": {"category": "evidence", "evidence_state": "VERIFIED"},
    "evidence": {"category": "evidence"},
    "certificate": {"category": "certificates"},
    "story": {"category": "stories_lessons"},
    "lesson": {"category": "stories_lessons"},
    "project": {"category": "completed_projects"},
}


def derive_filter(query: str) -> dict:
    """Deterministic keyword->filter mapping for the demo comparison."""
    tokens = set(tokenize(query))
    for keyword, filters in _FILTER_HINTS.items():
        if keyword in tokens:
            return filters
    return {"category": "evidence"}  # neutral default for comparison


def print_result(result: RetrievalResult, text_chars: int = 160) -> None:
    print(f"\nSTRATEGY: {result.strategy.upper()}")
    print("-" * 60)
    if not result.documents:
        print("  (no documents returned)")
    for doc in result.documents:
        text = " ".join(doc.content.split())
        print(f"\n  {doc.rank}. source={doc.source}")
        print(f"     score={doc.score:.4f}  ({result.diagnostics.get('score_semantics', '')})")
        hint = _strategy_specific_hint(result.strategy, doc)
        if hint:
            print(f"     {hint}")
        print(f"     text={text[:text_chars]}{'…' if len(text) > text_chars else ''}")


def _strategy_specific_hint(strategy: str, doc) -> str:
    if strategy == "hybrid":
        v = doc.metadata.get("vector_rank")
        b = doc.metadata.get("bm25_rank")
        parts = []
        if v is not None:
            parts.append(f"vector_rank={v}")
        if b is not None:
            parts.append(f"bm25_rank={b}")
        return "rrf from " + ", ".join(parts)
    if strategy == "reranked":
        return f"pre-rerank rank={doc.metadata.get('pre_rerank_rank')}"
    if strategy == "multi_query":
        return f"best single-query rank={doc.rank}"
    return ""


def print_summary(results: dict[str, RetrievalResult], query: str,
                  filters: dict) -> None:
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for strategy in STRATEGY_ORDER:
        result = results.get(strategy)
        if result is None:
            continue
        line = f"{strategy.upper():<12} - documents returned: {len(result.documents)}"
        d = result.diagnostics
        if strategy == "multi_query":
            gen = d.get("generated_queries", [])
            fallback = d.get("llm_fallback_used")
            line += f" | generated queries: {len(gen)}"
            if fallback:
                line += " (LLM FALLBACK: original query only)"
        if strategy == "hybrid":
            line += (
                f" | vector candidates: {d.get('vector_candidates')}"
                f" | BM25 candidates: {d.get('bm25_candidates')}"
                f" | fused candidates: {d.get('fused_candidates')}"
                f" | k={d.get('rrf_k')}"
            )
        if strategy == "reranked":
            line += (
                f" | candidate pool: {d.get('candidate_pool')}"
                f" | final results: {d.get('final_results')}"
            )
        if strategy == "metadata":
            line += f" | filters: {d.get('filters_applied')}"
        latency = d.get("latency_ms")
        if latency is not None:
            line += f" | {latency}ms"
        print(line)
    _print_overlap(results)
    print(f"\n(metadata strategy used deterministic filter: {filters})")


def _print_overlap(results: dict[str, RetrievalResult]) -> None:
    """How much do strategies agree? High overlap = redundant; low = the
    strategies genuinely see the corpus differently."""
    sources = {
        strategy: {doc.source for doc in result.documents}
        for strategy, result in results.items()
    }
    vector = sources.get("vector", set())
    if vector:
        for strategy in ("bm25", "hybrid", "reranked"):
            other = sources.get(strategy, set())
            if other:
                overlap = len(vector & other)
                print(f"  overlap vector ∩ {strategy}: {overlap} of {len(vector)}")


def print_explanations(results: dict[str, RetrievalResult], query: str) -> None:
    """Deterministic WHY explanations — no LLM involved."""
    print("\n" + "=" * 60)
    print("WHY THE RESULTS DIFFER")
    print("=" * 60)
    query_tokens = set(tokenize(query))

    bm25 = results.get("bm25")
    if bm25 and bm25.documents:
        top = bm25.documents[0]
        doc_tokens = set(tokenize(top.content))
        shared = sorted(query_tokens & doc_tokens)
        if shared:
            # Which shared terms are rare (discriminating) in this chunk?
            corpus_rare = [t for t in shared if len(t) > 5][:5]
            shown = corpus_rare or shared[:5]
            print(
                f"\n• BM25 surfaced '{top.source}' because the query terms "
                f"{{{', '.join(shown)}}} appear LITERALLY in that chunk. "
                f"BM25 rewards exact term matches (weighted by rarity in the corpus)."
            )
    vector = results.get("vector")
    if vector and vector.documents:
        top = vector.documents[0]
        doc_tokens = set(tokenize(top.content))
        shared = sorted(query_tokens & doc_tokens)
        if len(shared) < 2:
            print(
                f"\n• Vector search surfaced '{top.source}' with almost NO query-term "
                f"overlap — the match is SEMANTIC: the chunk's meaning is close to "
                f"the query's meaning in embedding space, even though the words differ."
            )
    hybrid = results.get("hybrid")
    if hybrid and hybrid.documents:
        top = hybrid.documents[0]
        v, b = top.metadata.get("vector_rank"), top.metadata.get("bm25_rank")
        if v is not None and b is not None:
            print(
                f"\n• HYBRID promoted '{top.source}' to #1 because BOTH strategies "
                f"ranked it (vector rank {v}, BM25 rank {b}) — RRF rewards agreement "
                f"across independent rankings even when each rank is modest."
            )
        elif v is not None:
            print(
                f"\n• HYBRID's #1 '{top.source}' was vector-only (BM25 didn't rank it): "
                f"no exact query term appears in it, but its meaning matched."
            )
    reranked = results.get("reranked")
    if reranked and reranked.documents:
        top = reranked.documents[0]
        pre = top.metadata.get("pre_rerank_rank")
        if pre and pre != 1:
            print(
                f"\n• RERANKING moved '{top.source}' from fusion rank {pre} to #1: the "
                f"cross-encoder read the query AND the full chunk together and scored "
                f"their interaction as most relevant. Bi-encoder similarity can't "
                f"capture this — the query and document never 'saw' each other."
            )
    mq = results.get("multi_query")
    if mq:
        gen = mq.diagnostics.get("generated_queries", [])
        fallback = mq.diagnostics.get("llm_fallback_used")
        if fallback:
            print(
                "\n• MULTI-QUERY ran in FALLBACK (OpenRouter call failed or no key): "
                "only the original query was used, so its results equal plain vector "
                "search. Set a valid OPENAI_API_KEY (OpenRouter key) in .env to see "
                "the expansion effect."
            )
        elif gen:
            print(
                f"\n• MULTI-QUERY searched {len(gen) + 1} phrasings ({', '.join(gen[:3])}…), "
                f"unioned and deduplicated the results — catching chunks that one "
                f"phrasing of the question would miss."
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.retrieval.compare",
        description="Run one question through all retrieval strategies, side by side.",
    )
    parser.add_argument("query", help="The question to compare strategies on.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--strategies", nargs="*", default=None,
        help="Subset of strategies to run (default: all six).",
    )
    args = parser.parse_args(argv)

    setup_logging()
    strategies = tuple(args.strategies) if args.strategies else STRATEGY_ORDER
    unknown = set(strategies) - set(STRATEGIES)
    if unknown:
        print(f"Unknown strategies: {sorted(unknown)}. Valid: {list(STRATEGIES)}")
        return 2

    engine = RetrievalEngine()
    filters = derive_filter(args.query)
    print(f"QUESTION: {args.query!r}")
    print(f"top_k={args.top_k}")

    results = {}
    for strategy in strategies:
        try:
            if strategy == "metadata":
                results[strategy] = engine.retrieve(
                    args.query, strategy="metadata", top_k=args.top_k, filters=filters
                )
            else:
                results[strategy] = engine.retrieve(
                    args.query, strategy=strategy, top_k=args.top_k
                )
        except Exception as exc:
            print(f"\nSTRATEGY: {strategy.upper()} — FAILED: {exc}")
        print_result(results[strategy]) if strategy in results else None

    if results:
        print_summary(results, args.query, filters)
        print_explanations(results, args.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
