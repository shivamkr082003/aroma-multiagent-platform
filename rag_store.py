"""Shared vector store: embedding model, Qdrant collection and helpers.

Configuration (environment variables):
- EMBEDDING_PROVIDER: "local" (default, free, runs on CPU) or "openai"
  (needs OPENAI_API_KEY).
- LOCAL_EMBEDDING_MODEL: sentence-transformers model for "local"
  (default BAAI/bge-small-en-v1.5, 384 dims, ~130 MB download on first use).
- QDRANT_URL: Qdrant server (default http://localhost:6333).
- QDRANT_API_KEY: required for Qdrant Cloud, unset for a local Qdrant.
- QDRANT_COLLECTION: override the collection name. By default each
  embedding model gets its own collection, because vectors from different
  models can't be searched together.
"""

import logging
import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

load_dotenv()

logger = logging.getLogger("aroma.rag")

# QDRANT_API_KEY is only needed for Qdrant Cloud; a local Qdrant has none.
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                             api_key=os.getenv("QDRANT_API_KEY") or None)

# Payload fields every search filters on; indexed so filtering stays fast as data grows.
_INDEXED_FIELDS = ("metadata.user_id", "metadata.session_id", "metadata.project_id", "metadata.file_id",
                   "metadata.file_hash")


class LocalEmbeddings(Embeddings):
    """sentence-transformers model, loaded once per process."""

    # BGE models retrieve better when queries (not documents) carry this instruction.
    _BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")
        self._query_prefix = self._BGE_QUERY_PREFIX if "bge" in model_name.lower() else ""

    @property
    def dimension(self) -> int:
        # Renamed in sentence-transformers 5.x; support both.
        getter = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        return getter()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, batch_size=32, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(self._query_prefix + text, normalize_embeddings=True).tolist()


def _provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    if _provider() == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")
    return LocalEmbeddings(os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))


def embedding_dimension() -> int:
    embeddings = get_embeddings()
    return embeddings.dimension if isinstance(embeddings, LocalEmbeddings) else 1536


def collection_name() -> str:
    configured = os.getenv("QDRANT_COLLECTION", "").strip()
    if configured:
        return configured
    if _provider() == "openai":
        return "docs"  # the original collection, kept for existing OpenAI-embedded data
    model = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").split("/")[-1]
    return "docs_" + re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")


def ensure_collection() -> None:
    """Create the collection and payload indexes if they don't exist yet."""
    name = collection_name()
    if not qdrant_client.collection_exists(name):
        qdrant_client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=embedding_dimension(), distance=Distance.COSINE),
        )
        for field in _INDEXED_FIELDS:
            qdrant_client.create_payload_index(name, field_name=field, field_schema=PayloadSchemaType.KEYWORD)
        logger.info("Created Qdrant collection %s", name)


def split_documents(docs: list) -> list:
    """The one chunking setup, shared by uploads and the evaluation harness."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100).split_documents(docs)


def get_vectorstore() -> QdrantVectorStore:
    return QdrantVectorStore(client=qdrant_client, collection_name=collection_name(), embedding=get_embeddings())


def session_has_docs(session_id: str, user_id: str, project_id: str | None = None) -> bool:
    """True if this chat (or the project it belongs to) has any of the user's documents."""
    from retrieval import scope_filter

    try:
        result = qdrant_client.count(
            collection_name=collection_name(),
            count_filter=scope_filter(user_id, session_id, project_id=project_id),
            exact=True,
        )
        return result.count > 0
    except Exception as exc:
        logger.warning("Could not check session documents: %s", exc)
        return False
