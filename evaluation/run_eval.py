"""Evaluate Aroma's document retrieval (and optionally its answers).

    python -m evaluation.run_eval              # retrieval metrics only (no API calls)
    python -m evaluation.run_eval --answers    # + LLM-judged answer quality (uses Groq)
    python -m evaluation.run_eval --answers --limit 10   # judge only the first 10 (saves API quota)

The corpus (evaluation/corpus) is chunked and embedded exactly like an upload,
into an in-memory Qdrant, so real data is never touched. Every question in
evaluation/questions.json has a "gold" snippet; a retrieved chunk counts as
relevant when it contains that snippet.

Retrieval metrics (per mode, overall and per question type):
- Hit@k   share of questions whose gold chunk is in the top k
- MRR     mean of 1/rank of the first gold chunk (0 if not in the top 5)
- latency per query

Answer metrics (RAGAS-style, judged by an LLM):
- correctness   does the answer agree with the reference answer?
- faithfulness  is every claim in the answer supported by the retrieved context?
"""

import argparse
import glob
import json
import os
import statistics
import sys
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from rag_store import embedding_dimension, get_embeddings, split_documents  # noqa: E402
from retrieval import MODES, retrieve, scope_filter  # noqa: E402

COLLECTION = "eval"
USER, SESSION = "eval-user", "eval-session"
K = 5


def build_index() -> tuple[QdrantClient, QdrantVectorStore, int]:
    client = QdrantClient(":memory:")
    client.create_collection(COLLECTION, vectors_config=VectorParams(size=embedding_dimension(), distance=Distance.COSINE))
    docs = [
        Document(page_content=Path(path).read_text(), metadata={"file_name": Path(path).name})
        for path in sorted(glob.glob(str(ROOT / "corpus" / "*.txt")))
    ]
    chunks = split_documents(docs)
    for chunk in chunks:
        chunk.metadata.update(user_id=USER, session_id=SESSION, file_id=chunk.metadata["file_name"])
    store = QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=get_embeddings())
    store.add_documents(chunks)
    return client, store, len(chunks)


def first_gold_rank(docs: list[Document], gold: str) -> int | None:
    for rank, doc in enumerate(docs, start=1):
        if gold in doc.page_content:
            return rank
    return None


def summarize(rows: list[dict]) -> dict:
    ranks = [r["rank"] for r in rows]
    return {
        "n": len(rows),
        "hit@1": round(sum(1 for r in ranks if r == 1) / len(rows), 3),
        "hit@3": round(sum(1 for r in ranks if r and r <= 3) / len(rows), 3),
        "hit@5": round(sum(1 for r in ranks if r and r <= 5) / len(rows), 3),
        "mrr": round(sum(1 / r for r in ranks if r) / len(rows), 3),
        "latency_ms_p50": round(statistics.median(r["ms"] for r in rows), 1),
    }


def evaluate_retrieval(client, store, questions) -> dict:
    flt = scope_filter(USER, SESSION)
    results = {}
    for mode in MODES:
        # Warm up once so model loading isn't counted as query latency.
        retrieve("warm up", flt, store=store, client=client, collection=COLLECTION, k=K, mode=mode)
        rows = []
        for q in questions:
            start = time.perf_counter()
            docs = retrieve(q["question"], flt, store=store, client=client, collection=COLLECTION, k=K, mode=mode)
            ms = (time.perf_counter() - start) * 1000
            rows.append({"question": q["question"], "type": q["type"], "rank": first_gold_rank(docs, q["gold"]),
                         "ms": ms, "docs": docs})
        results[mode] = {
            "overall": summarize(rows),
            "exact": summarize([r for r in rows if r["type"] == "exact"]),
            "semantic": summarize([r for r in rows if r["type"] == "semantic"]),
            "rows": rows,
        }
    return results


# ===========================
#  ANSWER QUALITY (LLM judge)
# ===========================
def _llm(temperature: float):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="openai/gpt-oss-120b", temperature=temperature, timeout=60, max_retries=4,
                      api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")


JUDGE_PROMPT = """You are grading a question-answering system. Reply with ONLY a JSON object:
{{"correct": true|false, "faithful": true|false}}

- "correct": the answer gives the same key facts as the reference answer (wording may differ;
  extra correct detail is fine; missing or wrong key facts are not).
- "faithful": every factual claim in the answer is supported by the context. An answer that
  says the context does not contain the information is faithful.

Question: {question}
Reference answer: {reference}

Context:
{context}

Answer to grade:
{answer}"""


def evaluate_answers(questions, retrieval: dict, modes: list[str], limit: int | None = None) -> dict:
    answerer, judge = _llm(0.3), _llm(0.0)
    results = {}
    for mode in modes:
        rows = []
        for q, r in list(zip(questions, retrieval[mode]["rows"]))[:limit]:
            context = "\n\n".join(f"[{i}] {d.page_content}" for i, d in enumerate(r["docs"], start=1))
            answer = answerer.invoke(
                f"Answer the question using only the context. Be concise.\n\nContext:\n{context}\n\nQuestion: {q['question']}"
            ).content
            verdict = {"correct": False, "faithful": False}
            for _ in range(3):  # the judge occasionally wraps JSON in prose; retry
                raw = judge.invoke(JUDGE_PROMPT.format(question=q["question"], reference=q["answer"],
                                                       context=context, answer=answer)).content
                try:
                    verdict = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
                    break
                except ValueError:
                    continue
            rows.append({"question": q["question"], "type": q["type"], "answer": answer, **verdict})
            print(f"  [{mode}] {'✓' if verdict.get('correct') else '✗'} {q['question'][:70]}", flush=True)
        results[mode] = {
            "correctness": round(sum(bool(r["correct"]) for r in rows) / len(rows), 3),
            "faithfulness": round(sum(bool(r["faithful"]) for r in rows) / len(rows), 3),
            "rows": rows,
        }
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--answers", action="store_true", help="also judge generated answers with the LLM (Groq)")
    parser.add_argument("--limit", type=int, help="judge only the first N questions (each costs 2 LLM calls per mode)")
    parser.add_argument("--out", default=str(ROOT.parent / "benchmark-results" / "retrieval-eval.json"))
    args = parser.parse_args()

    questions = json.loads((ROOT / "questions.json").read_text())
    client, store, n_chunks = build_index()
    print(f"Indexed {n_chunks} chunks from {len(glob.glob(str(ROOT / 'corpus' / '*.txt')))} documents; "
          f"{len(questions)} questions.\n")

    retrieval = evaluate_retrieval(client, store, questions)

    print(f"{'mode':<15}{'Hit@1':>8}{'Hit@3':>8}{'Hit@5':>8}{'MRR':>8}   {'exact MRR':>10}{'semantic MRR':>14}{'p50 ms':>9}")
    for mode, res in retrieval.items():
        o = res["overall"]
        print(f"{mode:<15}{o['hit@1']:>8.3f}{o['hit@3']:>8.3f}{o['hit@5']:>8.3f}{o['mrr']:>8.3f}   "
              f"{res['exact']['mrr']:>10.3f}{res['semantic']['mrr']:>14.3f}{o['latency_ms_p50']:>9.1f}")

    report = {
        "corpus_chunks": n_chunks,
        "questions": len(questions),
        "k": K,
        "embedding_model": os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        "retrieval": {
            mode: {key: val for key, val in res.items() if key != "rows"}
                  | {"misses": [r["question"] for r in res["rows"] if not r["rank"]]}
            for mode, res in retrieval.items()
        },
    }

    if args.answers:
        print("\nJudging answers (baseline vs best)…")
        answers = evaluate_answers(questions, retrieval, ["dense_mmr", "hybrid_rerank"], args.limit)
        report["answers"] = answers
        print(f"\n{'mode':<15}{'correctness':>13}{'faithfulness':>14}")
        for mode, res in answers.items():
            print(f"{mode:<15}{res['correctness']:>13.3f}{res['faithfulness']:>14.3f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
