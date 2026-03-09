"""
Debate mode writers — Optimist and Skeptic perspectives.
Two agents that argue different sides, used in debate pipeline.
"""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import config

OPTIMIST_PROMPT = """You are the OPTIMIST researcher. You write a report that
emphasizes the POSITIVE aspects, opportunities, benefits, and promising developments
of the topic. You present the best-case scenario backed by evidence from the research.

Rules:
- Use the research data provided — do not invent facts
- Focus on opportunities, successes, upward trends, positive impacts
- Acknowledge challenges only briefly, then pivot to solutions
- Write 600-800 words in professional Markdown
- Start with a title: # [Topic]: The Optimist's Perspective
- Include a ## Opportunities & Strengths section
- End with ## Why This Matters Positively
- Include source URLs where available
"""

SKEPTIC_PROMPT = """You are the SKEPTIC researcher. You write a report that
emphasizes the RISKS, challenges, limitations, and concerning trends of the topic.
You present the critical analysis backed by evidence from the research.

Rules:
- Use the research data provided — do not invent facts
- Focus on risks, failures, downward trends, unintended consequences
- Acknowledge positives only briefly, then highlight the caveats
- Write 600-800 words in professional Markdown
- Start with a title: # [Topic]: The Skeptic's Analysis
- Include a ## Risks & Weaknesses section
- End with ## What We Should Be Concerned About
- Include source URLs where available
"""


def run_optimist(analysis: str, query: str) -> str:
    """Write the optimistic perspective report."""
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0.5,
        api_key=config.GROQ_API_KEY,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", OPTIMIST_PROMPT),
        ("human", "Topic: {query}\n\nResearch analysis:\n{analysis}\n\n"
                  "Write your optimist perspective report now."),
    ])
    return (prompt | llm | StrOutputParser()).invoke({
        "analysis": analysis,
        "query": query,
    })


def run_skeptic(analysis: str, query: str) -> str:
    """Write the skeptic/critical perspective report."""
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0.5,
        api_key=config.GROQ_API_KEY,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", SKEPTIC_PROMPT),
        ("human", "Topic: {query}\n\nResearch analysis:\n{analysis}\n\n"
                  "Write your skeptic analysis report now."),
    ])
    return (prompt | llm | StrOutputParser()).invoke({
        "analysis": analysis,
        "query": query,
    })
