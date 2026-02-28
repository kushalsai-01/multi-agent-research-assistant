import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

RESEARCHER = "researcher"
ANALYST = "analyst"
WRITER = "writer"
REVIEWER = "reviewer"

MAX_SEARCH_RESULTS = 6
MAX_REPORT_WORDS = 1500
