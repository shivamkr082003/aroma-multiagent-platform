"""Document ingestion: text extraction, chunking, embedding, listing, deletion.

Used by chat uploads (scoped to one chat) and project uploads (shared by every
chat in the project). Chunks carry their scope in Qdrant payload metadata:
user_id always, plus session_id or project_id.
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone

import fitz
from langchain_community.document_loaders import Docx2txtLoader, TextLoader
from langchain_core.documents import Document
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

from rag_store import collection_name, get_vectorstore, qdrant_client, split_documents

GAP_THRESHOLD_PT = 1.5
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".docx")


def _reconstruct_line(spans: list[tuple[float, float, str]]) -> str:
    """
    spans: list of (x0, x1, text) for one visual line, sorted by x0.
    Inserts a space wherever the horizontal gap between spans exceeds
    GAP_THRESHOLD_PT — purely based on geometry, no word lists, no
    domain knowledge. Works identically for names, URLs, code, numbers,
    or anything else.
    """
    if not spans:
        return ""
    out = spans[0][2]
    prev_x1 = spans[0][1]
    for x0, x1, text in spans[1:]:
        gap = x0 - prev_x1
        if gap > GAP_THRESHOLD_PT and not out.endswith(" ") and not text.startswith(" "):
            out += " "
        out += text
        prev_x1 = x1
    return out
 
 
def extract_pdf_text_layout_aware(file_path: str) -> list[Document]:
    """
    Extract text from a PDF using span-level layout data so visually
    separate text (different columns, icon-prefixed rows, adjacent
    links with no embedded space) gets a space between it, even when
    the PDF itself never included a space character there. Returns one
    LangChain Document per page.
    """
    docs = []
    pdf = fitz.open(file_path)
 
    for page_num, page in enumerate(pdf):
        raw = page.get_text("dict")
        lines_text = []
 
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                spans = []
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append((x0, x1, text))
                spans.sort(key=lambda s: s[0])  # left to right
                if spans:
                    lines_text.append(_reconstruct_line(spans))
 
        page_text = "\n".join(lines_text)
        docs.append(
            Document(
                page_content=page_text,
                metadata={"source": file_path, "page": page_num},
            )
        )
 
    pdf.close()
    return docs
 
 
def load_document(file_location: str, ext: str):
    """Load a document with the best available extraction for its type."""
    if ext == ".pdf":
        return extract_pdf_text_layout_aware(file_location)
    elif ext == ".txt":
        return TextLoader(file_location).load()
    elif ext == ".docx":
        return Docx2txtLoader(file_location).load()
    else:
        return None
 
 
# ===========================
#  DUPLICATE UPLOAD DETECTION
#
#  Hash the raw file bytes (content-based, not filename-based — so a
#  renamed copy of the same PDF is still recognized as a duplicate).
#  Before chunking/embedding, check Qdrant for any existing chunk with
#  the same file_hash. If found, skip processing entirely and just
#  return the existing file_id — silently, with no indication to the
#  user that this was a duplicate. The response shape is identical
#  either way, so the frontend can't tell the difference.
# ===========================
def compute_file_hash(file_bytes: bytes) -> str:
    """SHA-256 hash of the raw file contents."""
    return hashlib.sha256(file_bytes).hexdigest()


def _scope(user_id: str, *, session_id: str | None = None, project_id: str | None = None,
           file_id: str | None = None, file_hash: str | None = None) -> Filter:
    must = [FieldCondition(key="metadata.user_id", match=MatchValue(value=user_id))]
    for key, value in (("session_id", session_id), ("project_id", project_id),
                       ("file_id", file_id), ("file_hash", file_hash)):
        if value:
            must.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
    return Filter(must=must)


def find_existing_file_id(file_hash: str, user_id: str, *, session_id: str | None = None,
                          project_id: str | None = None) -> str | None:
    """
    Look up Qdrant for a chunk this user already stored with this exact
    file_hash in the same chat or project. Scoped per user so one user can
    never receive another user's file_id, and per chat/project because
    retrieval filters chunks by that scope: reusing a file_id from elsewhere
    would leave this chat with no searchable document.
    """
    results, _ = qdrant_client.scroll(
        collection_name=collection_name(),
        scroll_filter=_scope(user_id, session_id=session_id, project_id=project_id, file_hash=file_hash),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if results:
        payload = results[0].payload or {}
        # langchain-qdrant nests user metadata under "metadata"
        return payload.get("metadata", payload).get("file_id")
    return None


def ingest(file_bytes: bytes, filename: str, *, user_id: str, session_id: str | None = None,
           project_id: str | None = None) -> str | None:
    """Store a document for one chat or one project. Returns its file_id, or None if unsupported.

    Blocking (extraction + embedding on the CPU): call it in a thread pool.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return None

    # Hash the raw content: a renamed copy of the same file is still a duplicate,
    # and re-uploading it in the same scope silently reuses the stored chunks.
    file_hash = compute_file_hash(file_bytes)
    existing = find_existing_file_id(file_hash, user_id, session_id=session_id, project_id=project_id)
    if existing:
        return existing

    file_id = str(uuid.uuid4())
    file_location = f"temp_{file_id}{ext}"
    with open(file_location, "wb") as f:
        f.write(file_bytes)
    try:
        docs = load_document(file_location, ext)
        if not docs:
            return None
        chunks = split_documents(docs)
        uploaded_at = datetime.now(timezone.utc).isoformat()
        for chunk in chunks:
            chunk.metadata.update(
                file_id=file_id, user_id=user_id, file_hash=file_hash,
                file_name=filename,  # shown in citations
                uploaded_at=uploaded_at,
            )
            if session_id:
                chunk.metadata["session_id"] = session_id
            if project_id:
                chunk.metadata["project_id"] = project_id
        get_vectorstore().add_documents(chunks)
    finally:
        os.remove(file_location)
    return file_id


def list_documents(user_id: str, *, session_id: str | None = None, project_id: str | None = None) -> list[dict]:
    """One entry per file in scope, newest first."""
    files: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=collection_name(),
            scroll_filter=_scope(user_id, session_id=session_id, project_id=project_id),
            limit=256, offset=offset, with_payload=True, with_vectors=False,
        )
        for point in points:
            meta = (point.payload or {}).get("metadata", {})
            entry = files.setdefault(meta.get("file_id"), {
                "file_id": meta.get("file_id"),
                "file_name": meta.get("file_name") or "Document",
                "uploaded_at": meta.get("uploaded_at"),
                "chunks": 0,
            })
            entry["chunks"] += 1
        if offset is None:
            break
    return sorted(files.values(), key=lambda f: f["uploaded_at"] or "", reverse=True)


def delete_documents(user_id: str, *, session_id: str | None = None, project_id: str | None = None,
                     file_id: str | None = None) -> None:
    if not (session_id or project_id or file_id):
        raise ValueError("Refusing to delete every document of a user; pass a scope.")
    qdrant_client.delete(
        collection_name=collection_name(),
        points_selector=FilterSelector(filter=_scope(user_id, session_id=session_id, project_id=project_id,
                                                     file_id=file_id)),
    )


def count_documents(user_id: str) -> int:
    return len({d["file_id"] for d in list_documents(user_id)})
