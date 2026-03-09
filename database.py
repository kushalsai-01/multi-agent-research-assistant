"""
Supabase database integration.
Set SUPABASE_URL and SUPABASE_KEY in your .env to enable persistence.
If not configured, the app still works — reports just won't be stored.
"""

import os
from datetime import datetime, timezone
from typing import Optional

try:
    from supabase import create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _SUPABASE_AVAILABLE:
        return None
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None
    _client = create_client(url, key)
    return _client


def save_report(topic: str, final_report: str, raw_research: str = "", analysis: str = "") -> Optional[str]:
    """Save a completed report to Supabase. Returns the row ID or None."""
    client = _get_client()
    if not client:
        return None
    try:
        result = client.table("reports").insert({
            "topic": topic,
            "final_report": final_report,
            "raw_research": raw_research,
            "analysis": analysis,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception as e:
        print(f"[Supabase] save_report failed: {e}")
    return None


def get_reports(limit: int = 20) -> list:
    """Return a list of recent reports (id, topic, created_at only)."""
    client = _get_client()
    if not client:
        return []
    try:
        result = (
            client.table("reports")
            .select("id, topic, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[Supabase] get_reports failed: {e}")
        return []


def get_report(report_id: str) -> Optional[dict]:
    """Return a single full report by ID."""
    client = _get_client()
    if not client:
        return None
    try:
        result = (
            client.table("reports")
            .select("*")
            .eq("id", report_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        print(f"[Supabase] get_report failed: {e}")
        return None
