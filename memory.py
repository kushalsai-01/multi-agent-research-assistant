"""
Session memory for agent personalization across research runs.
Stores the last 10 queries per session in-memory (resets on restart).
Optionally persists to Supabase if configured.

Usage:
    from memory import remember_query, get_memory, suggest_related
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from database import _get_client

# In-memory store: session_id -> list of {query, report_id, timestamp}
_sessions: Dict[str, List[dict]] = {}
MAX_PER_SESSION = 10


def remember_query(session_id: str, query: str, report_id: Optional[str] = None) -> None:
    """Store a query for a session."""
    if not session_id:
        return
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({
        "query": query,
        "report_id": report_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only last N
    _sessions[session_id] = _sessions[session_id][-MAX_PER_SESSION:]

    # Optionally persist to Supabase (user_sessions table — gracefully skipped if absent)
    try:
        client = _get_client()
        if client:
            client.table("user_sessions").upsert({
                "session_id": session_id,
                "queries": _sessions[session_id],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
    except Exception:
        pass  # table might not exist yet; memory still works in-process


def get_memory(session_id: str) -> List[dict]:
    """Return list of past queries for a session."""
    if not session_id:
        return []

    # Try in-memory first
    if session_id in _sessions:
        return _sessions[session_id]

    # Fall back to Supabase
    try:
        client = _get_client()
        if client:
            result = (
                client.table("user_sessions")
                .select("queries")
                .eq("session_id", session_id)
                .single()
                .execute()
            )
            if result.data:
                queries = result.data.get("queries", [])
                _sessions[session_id] = queries  # cache locally
                return queries
    except Exception:
        pass
    return []


def get_context_hint(session_id: str, current_query: str) -> str:
    """Return a context string of past topics to enrich agent prompts."""
    past = get_memory(session_id)
    if not past:
        return ""
    recent = [p["query"] for p in past[-3:] if p["query"] != current_query]
    if not recent:
        return ""
    topics = "; ".join(recent)
    return f"\n\n[User has previously researched: {topics}. Consider cross-referencing where relevant.]"
