import hashlib

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

import retrieval
from retrieval import reciprocal_rank_fusion, retrieve, scope_filter, tokenize


class HashEmbeddings(Embeddings):
    """Deterministic bag-of-words vectors: no model download, enough to rank by word overlap."""

    dim = 64

    def _embed(self, text):
        vec = [0.0] * self.dim
        for token in tokenize(text):
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)


CHUNKS = [
    ("The hostel gates close at 10:30 PM on weekdays.", "u1", "s1"),
    ("The anti-ragging helpline number is 1800-180-5522.", "u1", "s1"),
    ("Mess dinner is served from 7:30 PM to 9:30 PM.", "u1", "s1"),
    ("Secret of another user: helpline 1800-180-5522.", "u2", "s9"),
]


@pytest.fixture
def index():
    client = QdrantClient(":memory:")
    client.create_collection("t", vectors_config=VectorParams(size=HashEmbeddings.dim, distance=Distance.COSINE))
    store = QdrantVectorStore(client=client, collection_name="t", embedding=HashEmbeddings())
    store.add_documents([
        Document(page_content=text, metadata={"user_id": user, "session_id": session, "file_id": "f"})
        for text, user, session in CHUNKS
    ])
    return client, store


def test_tokenize_keeps_numbers_whole():
    assert tokenize("Budget: 42,500 rupees, F1 0.873!") == ["budget", "42,500", "rupees", "f1", "0.873"]


def test_rrf_rewards_documents_ranked_well_by_both_lists():
    a, b, c = (Document(page_content=x) for x in "abc")
    fused = reciprocal_rank_fusion([[a, b, c], [b, c, a]])
    assert [d.page_content for d in fused] == ["b", "a", "c"]


@pytest.mark.parametrize("mode", ["dense_mmr", "dense", "hybrid", "hybrid_rerank"])
def test_every_mode_stays_inside_the_users_scope(index, monkeypatch, mode):
    monkeypatch.setattr(retrieval, "rerank", lambda query, docs, k: docs[:k])  # skip model download
    client, store = index
    docs = retrieve("helpline 1800-180-5522", scope_filter("u1", "s1"), store=store, client=client,
                    collection="t", k=3, mode=mode)
    assert docs and all(d.metadata["user_id"] == "u1" for d in docs)


def test_bm25_finds_exact_numbers(index):
    client, _ = index
    docs = retrieval.bm25_search(client, "t", "what is 1800-180-5522", scope_filter("u1", "s1"), k=3)
    assert docs[0].page_content.startswith("The anti-ragging helpline")


def test_hybrid_rerank_uses_the_reranker_order(index, monkeypatch):
    client, store = index
    seen = {}

    def fake_rerank(query, docs, k):
        seen["candidates"] = len(docs)
        return list(reversed(docs))[:k]

    monkeypatch.setattr(retrieval, "rerank", fake_rerank)
    docs = retrieve("dinner time", scope_filter("u1", "s1"), store=store, client=client, collection="t", k=2,
                    mode="hybrid_rerank")
    assert seen["candidates"] == 3 and len(docs) == 2


def test_unknown_mode_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_MODE", "nonsense")
    assert retrieval.current_mode() == "hybrid_rerank"
