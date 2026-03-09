"""
RAG (Retrieval-Augmented Generation) using Supabase pgvector.
Uses sentence-transformers for free local embeddings (no OpenAI needed).
Model: all-MiniLM-L6-v2 (384 dimensions, ~22MB, runs on CPU)

Gracefully degrades — if sentence-transformers is not installed or
Supabase is not configured, all functions return None/[].
"""
import os
from typing import Optional, List
from database import _get_client

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return _embedder
    except ImportError:
        print("[RAG] sentence-transformers not installed. RAG disabled.")
        return None
    except Exception as e:
        print(f"[RAG] Failed to load embedding model: {e}")
        return None


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a text string into a 384-dim vector."""
    embedder = _get_embedder()
    if not embedder:
        return None
    vec = embedder.encode(text, normalize_embeddings=True)
    return vec.tolist()


def search_similar_reports(query: str, threshold: float = 0.85, top_k: int = 3) -> List[dict]:
    """Search for semantically similar past reports."""
    client = _get_client()
    if not client:
        return []
    embedding = embed_text(query)
    if not embedding:
        return []
    try:
        result = client.rpc("search_similar_reports", {
            "query_embedding": embedding,
            "similarity_threshold": threshold,
            "match_count": top_k,
        }).execute()
        return result.data or []
    except Exception as e:
        print(f"[RAG] search failed: {e}")
        return []


def store_report_embedding(report_id: str, topic: str, final_report: str) -> bool:
    """Store embedding for a report after it's saved."""
    client = _get_client()
    if not client:
        return False
    text_to_embed = f"{topic}\n\n{final_report[:2000]}"
    embedding = embed_text(text_to_embed)
    if not embedding:
        return False
    try:
        client.table("reports").update({"embedding": embedding}).eq("id", report_id).execute()
        return True
    except Exception as e:
        print(f"[RAG] store embedding failed: {e}")
        return False


def get_rag_context(query: str) -> Optional[dict]:
    """
    Returns the best matching cached report if similarity > threshold.
    Returns None if no good match found.
    """
    matches = search_similar_reports(query, threshold=0.85, top_k=1)
    if matches:
        return matches[0]
    return None
