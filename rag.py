"""
RAG (Retrieval-Augmented Generation) using Supabase full-text search.

Uses PostgreSQL ilike topic search — no local ML model, no PyTorch.
This keeps RAM usage on Render's free tier (512MB) well within limits.
Semantic vector search (pgvector) is skipped to avoid the 400-500MB
torch/sentence-transformers overhead that caused OOM restarts.

Gracefully degrades — if Supabase is not configured, returns None/[].
"""
import re
from typing import Optional, List
from database import _get_client

# Common English stop words to skip when building keyword search
_STOP = {
    "the", "is", "in", "it", "of", "and", "or", "to", "a", "an", "for",
    "on", "with", "that", "this", "are", "was", "be", "by", "at", "from",
    "as", "how", "what", "why", "when", "where", "which", "who", "will",
    "can", "do", "does", "has", "have", "had", "not", "but",
}


def _keywords(text: str) -> List[str]:
    """Extract meaningful keywords from a query string."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return [w for w in words if w not in _STOP][:5]


def search_similar_reports(query: str, threshold: float = 0.85, top_k: int = 3) -> List[dict]:
    """
    Search for past reports whose topic overlaps with query keywords.
    Uses Supabase ilike on the topic column — zero RAM overhead.
    The `threshold` param is kept for API compatibility but not used (text search).
    """
    client = _get_client()
    if not client:
        return []

    keywords = _keywords(query)
    if not keywords:
        return []

    seen: set = set()
    results: List[dict] = []

    for word in keywords:
        if len(results) >= top_k:
            break
        try:
            resp = (
                client.table("reports")
                .select("id, topic, final_report, created_at")
                .ilike("topic", f"%{word}%")
                .limit(top_k)
                .execute()
            )
            for row in (resp.data or []):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    results.append(row)
        except Exception as e:
            print(f"[RAG] search failed for keyword '{word}': {e}")
            continue

    return results[:top_k]


def store_report_embedding(report_id: str, topic: str, final_report: str) -> bool:
    """
    No-op on free tier — vector embeddings skipped to save RAM.
    Topic-based text search works without storing embeddings.
    To re-enable: install sentence-transformers and restore original logic.
    """
    return True


def get_rag_context(query: str) -> Optional[dict]:
    """
    Return the best matching cached report by topic keyword overlap.
    Returns None if no match found.
    """
    matches = search_similar_reports(query, top_k=1)
    if matches:
        return matches[0]
    return None
