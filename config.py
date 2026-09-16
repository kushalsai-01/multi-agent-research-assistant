import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Fallback model used automatically when primary hits rate limits / daily quota
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# LangSmith — set these to enable tracing at smith.langchain.com
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "ai-research-assistant")

if LANGCHAIN_TRACING_V2 == "true" and LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

PLANNER = "planner"
RESEARCHER = "researcher"
ANALYST = "analyst"
WRITER = "writer"
REVIEWER = "reviewer"

MAX_SEARCH_RESULTS = 6
MAX_REPORT_WORDS = 1500

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "research_documents")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
RAG_CHUNK_TOKENS = int(os.getenv("RAG_CHUNK_TOKENS", "320"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "64"))
RAG_PARENT_TOKENS = int(os.getenv("RAG_PARENT_TOKENS", "1100"))
RAG_RETRIEVAL_LIMIT = int(os.getenv("RAG_RETRIEVAL_LIMIT", "6"))
RAG_CANDIDATE_LIMIT = int(os.getenv("RAG_CANDIDATE_LIMIT", "30"))
RAG_MAX_CHUNKS_PER_PAGE = int(os.getenv("RAG_MAX_CHUNKS_PER_PAGE", "2"))
RAG_MIN_CHARS = int(os.getenv("RAG_MIN_CHARS", "80"))
RAG_EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "24"))
QDRANT_LOCAL_PATH = str(Path(__file__).parent / "data" / "qdrant")
DEPLOYMENT_ENV = os.getenv("DEPLOYMENT_ENV", "development").lower()


def deployment_issues() -> list[str]:
    required = {
        "GROQ_API_KEY": GROQ_API_KEY,
        "QDRANT_URL": QDRANT_URL,
        "QDRANT_API_KEY": QDRANT_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS", ""),
    }
    return [name for name, value in required.items() if not value]
_configured_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", ""
).split(",") if origin.strip()]
# Always permit Vite's two common local hostnames. Production origins remain
# explicitly controlled through CORS_ORIGINS.
CORS_ORIGINS = list(dict.fromkeys([
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *_configured_origins,
]))
