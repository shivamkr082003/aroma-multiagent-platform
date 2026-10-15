"""Document retrieval for RAG: dense, BM25, hybrid fusion and reranking.

Modes (RETRIEVAL_MODE env, default "hybrid_rerank"):
- dense_mmr      the original pipeline: vector search with MMR diversity.
- dense          plain vector (semantic) search.
- hybrid         vector + BM25 keyword search, merged with Reciprocal Rank Fusion.
- hybrid_rerank  hybrid candidates re-scored by a cross-encoder (RERANKER_MODEL,
                 default cross-encoder/ms-marco-MiniLM-L-6-v2, ~90 MB, CPU).

Why hybrid: embeddings match meaning ("who runs the project?" ~ "team lead")
but miss exact tokens such as names, IDs and numbers; BM25 is the opposite.
evaluation/run_eval.py measures each mode on a labelled question set.
"""

import os
import re
from functools import lru_cache

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rank_bm25 import BM25Okapi

MODES = ("dense_mmr", "dense", "hybrid", "hybrid_rerank")
CANDIDATES = 20  # how many results each retriever contributes before fusion/reranking
RRF_K = 60       # standard Reciprocal Rank Fusion constant

_TOKEN = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")


def current_mode() -> str:
    mode = os.getenv("RETRIEVAL_MODE", "hybrid_rerank").strip().lower()
    return mode if mode in MODES else "hybrid_rerank"


def scope_filter(user_id: str, session_id: str | None = None, file_id: str | None = None,
                 project_id: str | None = None) -> Filter:
    """Only this user's chunks: from one file, or from the chat plus its project."""
    owner = FieldCondition(key="metadata.user_id", match=MatchValue(value=user_id))
    if file_id:
        return Filter(must=[owner, FieldCondition(key="metadata.file_id", match=MatchValue(value=file_id))])
    # Qdrant: with "should" present, at least one of its conditions must match.
    should = [FieldCondition(key="metadata.session_id", match=MatchValue(value=session_id))]
    if project_id:
        should.append(FieldCondition(key="metadata.project_id", match=MatchValue(value=project_id)))
    return Filter(must=[owner], should=should)


def tokenize(text: str) -> list[str]:
    # Keeps numbers like "42,500" and "0.873" whole so exact figures can match.
    return _TOKEN.findall(text.lower())


# ===========================
#  RETRIEVERS
# ===========================
def dense_search(store, query: str, flt: Filter, k: int) -> list[Document]:
    return store.similarity_search(query, k=k, filter=flt)


def dense_mmr_search(store, query: str, flt: Filter, k: int) -> list[Document]:
    return store.max_marginal_relevance_search(query, k=k, fetch_k=k * 2, lambda_mult=0.5, filter=flt)


def _scope_chunks(client: QdrantClient, collection: str, flt: Filter, limit: int = 2000) -> list[Document]:
    """All chunks in scope. A chat holds a handful of documents, so this stays small."""
    points, _ = client.scroll(collection_name=collection, scroll_filter=flt, limit=limit,
                              with_payload=True, with_vectors=False)
    return [
        Document(page_content=(p.payload or {}).get("page_content", ""), metadata=(p.payload or {}).get("metadata", {}))
        for p in points
    ]


def bm25_search(client: QdrantClient, collection: str, query: str, flt: Filter, k: int) -> list[Document]:
    chunks = _scope_chunks(client, collection, flt)
    query_tokens = tokenize(query)
    if not chunks or not query_tokens:
        return []
    scores = BM25Okapi([tokenize(c.page_content) for c in chunks]).get_scores(query_tokens)
    ranked = sorted(zip(scores, range(len(chunks))), key=lambda pair: pair[0], reverse=True)
    return [chunks[i] for score, i in ranked[:k] if score > 0]


def reciprocal_rank_fusion(rankings: list[list[Document]], k: int = RRF_K) -> list[Document]:
    """Merge ranked lists: each appearance adds 1 / (k + rank). Robust to different score scales."""
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            key = doc.page_content
            docs.setdefault(key, doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return [docs[key] for key in sorted(scores, key=scores.get, reverse=True)]


@lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"), device="cpu")


def rerank(query: str, docs: list[Document], k: int) -> list[Document]:
    """A cross-encoder reads query and passage together: slower, but far more precise than vectors."""
    if len(docs) <= 1:
        return docs[:k]
    scores = get_reranker().predict([(query, d.page_content) for d in docs])
    ranked = sorted(zip(scores, range(len(docs))), key=lambda pair: pair[0], reverse=True)
    return [docs[i] for _, i in ranked[:k]]


# ===========================
#  ENTRY POINT
# ===========================
def retrieve(query: str, flt: Filter, *, store, client: QdrantClient, collection: str,
             k: int = 5, mode: str | None = None) -> list[Document]:
    mode = mode or current_mode()
    if mode == "dense_mmr":
        return dense_mmr_search(store, query, flt, k)
    if mode == "dense":
        return dense_search(store, query, flt, k)

    fused = reciprocal_rank_fusion([
        dense_search(store, query, flt, CANDIDATES),
        bm25_search(client, collection, query, flt, CANDIDATES),
    ])
    if mode == "hybrid":
        return fused[:k]
    return rerank(query, fused[:CANDIDATES], k)
