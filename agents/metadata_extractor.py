"""
Lightweight metadata extractor — runs in parallel with analyst.
Extracts structured entities from raw research text using regex + LLM.
"""
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import config

DATE_PATTERN = re.compile(
    r'\b(20\d{2}|19\d{2})\b'
    r'|\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
)
NUMBER_PATTERN = re.compile(
    r'\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|thousand|B|M|K))?\b'
    r'|\b\d+(?:\.\d+)?%\b'
    r'|\b\d+(?:,\d{3})+\b'
)

EXTRACT_PROMPT = """Extract key metadata from the research text. Be concise and factual.

Output ONLY this exact structure:
ENTITIES: [comma-separated list of important people, companies, organizations]
LOCATIONS: [comma-separated list of countries, cities, regions]
KEY_DATES: [comma-separated list of significant dates/years mentioned]
KEY_NUMBERS: [comma-separated list of important statistics, percentages, dollar amounts]
MAIN_CLAIMS: [3 bullet points of the most important factual claims]
RESEARCH_GAPS: [1-2 topics the research didn't cover]"""


def run_metadata_extractor(research_data: str, query: str) -> dict:
    """Extract structured metadata from raw research."""
    # Quick regex extraction (no LLM cost)
    years = list(set(DATE_PATTERN.findall(research_data)))
    numbers = NUMBER_PATTERN.findall(research_data)[:20]

    # LLM extraction for entities and claims
    try:
        llm = ChatGroq(
            model=config.GROQ_MODEL,
            temperature=0,
            api_key=config.GROQ_API_KEY,
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACT_PROMPT),
            ("human", "Research text (first 3000 chars):\n\n{text}"),
        ])
        result = (prompt | llm | StrOutputParser()).invoke({"text": research_data[:3000]})

        # Parse the structured output
        metadata = {
            "raw": result,
            "regex_years": [y[0] or y[1] for y in years if y[0] or y[1]][:10],
            "regex_numbers": numbers,
        }

        for line in result.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                metadata[key.strip().lower()] = val.strip()

        return metadata
    except Exception as e:
        return {"error": str(e), "regex_years": [], "regex_numbers": numbers}


def metadata_to_context(metadata: dict) -> str:
    """Format metadata as context string for the writer."""
    lines = ["## Extracted Metadata (Verified Facts)\n"]
    for key in ["entities", "locations", "key_dates", "key_numbers", "main_claims", "research_gaps"]:
        if metadata.get(key):
            lines.append(f"**{key.replace('_', ' ').title()}:** {metadata[key]}")
    return "\n".join(lines)
