from __future__ import annotations

import hashlib
import io
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, BinaryIO

import tiktoken
from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

import config

VECTOR_SIZE = 384
_client: QdrantClient | None = None
_embedder: SentenceTransformer | None = None
_tokenizer: Any | None = None


@dataclass(frozen=True)
class Chunk:
    document_id: str
    chunk_id: str
    page_number: int
    text: str
    parent_text: str
    section: str


def _qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=20) if config.QDRANT_URL else QdrantClient(path=config.QDRANT_LOCAL_PATH)
        if not _client.collection_exists(config.QDRANT_COLLECTION):
            _client.create_collection(collection_name=config.QDRANT_COLLECTION, vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE))
            if config.QDRANT_URL:
                _client.create_payload_index(config.QDRANT_COLLECTION, "owner_id", models.PayloadSchemaType.KEYWORD)
                _client.create_payload_index(config.QDRANT_COLLECTION, "document_id", models.PayloadSchemaType.KEYWORD)
    return _client


def _embeddings() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    return _embedder


def _embed(texts: list[str]) -> list[list[float]]:
    return _embeddings().encode(texts, batch_size=config.RAG_EMBEDDING_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False).tolist()


def _tokens(text: str) -> list[Any]:
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tokenizer = False
    if _tokenizer:
        return _tokenizer.encode(text, disallowed_special=())
    return re.findall(r"\S+\s*", text)


def _decode(tokens: list[Any]) -> str:
    return _tokenizer.decode(tokens).strip() if _tokenizer else "".join(tokens).strip()


def _section_and_paragraphs(text: str) -> list[tuple[str, str]]:
    section = "Document content"
    result: list[tuple[str, str]] = []
    for block in re.split(r"\n\s*\n", text):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        if len(block) < 160 and not re.search(r"[.!?]\s", block):
            section = block[:160]
            continue
        result.append((section, block))
    return result or [(section, re.sub(r"\s+", " ", text).strip())]


def _split_page(document_id: str, page_number: int, text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    parent: list[int] = []
    index = 0
    stride = config.RAG_CHUNK_TOKENS - config.RAG_CHUNK_OVERLAP
    for section, paragraph in _section_and_paragraphs(text):
        paragraph_tokens = _tokens(paragraph)
        parent = (parent + paragraph_tokens)[-config.RAG_PARENT_TOKENS:]
        for start in range(0, len(paragraph_tokens), stride):
            content = _decode(paragraph_tokens[start:start + config.RAG_CHUNK_TOKENS])
            if len(content) < config.RAG_MIN_CHARS:
                continue
            chunks.append(Chunk(document_id, f"{document_id}:{page_number}:{index}", page_number, content, _decode(parent), section))
            index += 1
    return chunks


def _pdf_pages(stream: BinaryIO) -> list[tuple[int, str]]:
    pages = [(number, (page.extract_text() or "").strip()) for number, page in enumerate(PdfReader(stream).pages, start=1)]
    extracted = [(number, text) for number, text in pages if text]
    if not extracted:
        raise ValueError("No extractable text found in this PDF.")
    return extracted


def ingest_pdf(upload_file: Any, owner_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", (upload_file.filename or "document.pdf").split("/")[-1])
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported.")
    data = upload_file.file.read()
    if not data:
        raise ValueError("The uploaded PDF is empty.")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"PDF must be smaller than {config.MAX_UPLOAD_MB} MB.")
    document_id = str(uuid.uuid4())
    chunks = [chunk for page, text in _pdf_pages(io.BytesIO(data)) for chunk in _split_page(document_id, page, text)]
    if not chunks:
        raise ValueError("No usable text chunks could be extracted from this PDF.")
    document_hash = hashlib.sha256(data).hexdigest()
    payloads = [{"owner_id": owner_id, "document_id": chunk.document_id, "chunk_id": chunk.chunk_id, "page_number": chunk.page_number, "chunk_text": chunk.text, "parent_text": chunk.parent_text, "section": chunk.section, "metadata": {"filename": filename, "content_hash": document_hash, **(metadata or {})}} for chunk in chunks]
    _qdrant().upsert(collection_name=config.QDRANT_COLLECTION, points=[models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload) for vector, payload in zip(_embed([chunk.text for chunk in chunks]), payloads)], wait=True)
    return {"id": document_id, "filename": filename, "chunks": len(chunks), "pages": len({chunk.page_number for chunk in chunks})}


def _owner_filter(owner_id: str, document_id: str | None = None) -> models.Filter:
    conditions = [models.FieldCondition(key="owner_id", match=models.MatchValue(value=owner_id))]
    if document_id:
        conditions.append(models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)))
    return models.Filter(must=conditions)


def list_documents(owner_id: str) -> list[dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    offset = None
    while True:
        points, offset = _qdrant().scroll(config.QDRANT_COLLECTION, scroll_filter=_owner_filter(owner_id), limit=256, with_payload=True, with_vectors=False, offset=offset)
        for point in points:
            payload = point.payload or {}
            document_id = payload.get("document_id")
            if document_id not in docs:
                docs[document_id] = {"id": document_id, "filename": payload.get("metadata", {}).get("filename", "PDF"), "chunks": 0}
            docs[document_id]["chunks"] += 1
        if offset is None:
            break
    return sorted(docs.values(), key=lambda document: document["filename"].lower())


def delete_document(document_id: str, owner_id: str) -> bool:
    if not any(document["id"] == document_id for document in list_documents(owner_id)):
        return False
    _qdrant().delete(config.QDRANT_COLLECTION, models.FilterSelector(filter=_owner_filter(owner_id, document_id)), wait=True)
    return True


def _terms(text: str) -> set[str]:
    ignored = {"with", "from", "that", "this", "what", "when", "where", "about", "into", "have", "will"}
    return {term for term in re.findall(r"[a-zA-Z0-9]{3,}", text.lower()) if term not in ignored}


def _rerank(query: str, hits: list[Any], limit: int) -> list[dict[str, Any]]:
    query_terms = _terms(query)
    candidates = []
    for hit in hits:
        payload = hit.payload or {}
        lexical = len(query_terms & _terms(payload.get("chunk_text", ""))) / max(len(query_terms), 1)
        candidates.append((0.82 * float(hit.score) + 0.18 * lexical, payload))
    selected: list[dict[str, Any]] = []
    page_counts: defaultdict[tuple[str, int], int] = defaultdict(int)
    for score, payload in sorted(candidates, key=lambda item: item[0], reverse=True):
        key = (payload.get("document_id", ""), payload.get("page_number", 0))
        if page_counts[key] >= config.RAG_MAX_CHUNKS_PER_PAGE or any(item["chunk_text"] == payload.get("chunk_text") for item in selected):
            continue
        selected.append({**payload, "score": round(score, 3)})
        page_counts[key] += 1
        if len(selected) == limit:
            break
    return selected


def retrieve_chunks(query: str, owner_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not query.strip() or not list_documents(owner_id):
        return []
    hits = _qdrant().query_points(config.QDRANT_COLLECTION, query=_embed([query])[0], query_filter=_owner_filter(owner_id), limit=config.RAG_CANDIDATE_LIMIT, with_payload=True).points
    return _rerank(query, hits, limit or config.RAG_RETRIEVAL_LIMIT)


def format_rag_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    blocks = ["## Retrieved document evidence\nUse only this evidence for PDF claims. Cite every used claim as [filename p.X]."]
    for chunk in chunks:
        filename = chunk.get("metadata", {}).get("filename", "Document")
        blocks.append(f"[Source: {filename} p.{chunk.get('page_number', '?')}; section: {chunk.get('section', 'Document content')}]\n{chunk.get('parent_text') or chunk.get('chunk_text', '')}")
    return "\n\n".join(blocks)


def get_rag_context(query: str):
    return None


def store_report_embedding(report_id: str, topic: str, final_report: str) -> bool:
    return True
