from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from agents.schemas import ReviewerOutput
import config

SYSTEM_PROMPT = """You are a Senior Editor and Quality Reviewer.

REVIEW PROCESS:
1. Check accuracy — are all claims supported by the research data?
2. Check completeness — are all key aspects of the topic covered?
3. Check clarity — is the writing clear, well-structured, and professional?
4. Check sources — are URLs cited properly?
5. Assign a quality_score from 1-10 based on overall quality.
6. If score >= 7: set passed=True, provide the polished report, empty revision_instructions.
7. If score < 7: set passed=False, provide the improved report AND specific revision_instructions
   for the writer to fix the remaining issues.

OUTPUT RULES:
- polished_report must be a COMPLETE Markdown report starting with # title.
- polished_report must be 800-1500 words.
- polished_report must include: title, executive summary blockquote, main sections, key takeaways, sources.
- Do NOT include scorecard, tables, or review commentary in the polished_report.
- strengths: list 2-3 strengths of the report.
- weaknesses: list 2-3 areas that need improvement (empty list if passed=True).
"""


def build_reviewer_chain():
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0.2,
        api_key=config.GROQ_API_KEY,
    )
    structured_llm = llm.with_structured_output(ReviewerOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Original topic: {query}\n\n"
                  "Research data available:\n{research_data}\n\n"
                  "Report to review and improve:\n{report}\n\n"
                  "Score this report, provide the polished version, and if score < 7 "
                  "give specific revision instructions."),
    ])

    return prompt | structured_llm


def run_reviewer(report: str, research_data: str, query: str) -> ReviewerOutput:
    """Run the reviewer chain and return structured ReviewerOutput."""
    chain = build_reviewer_chain()
    return chain.invoke({
        "report": report,
        "research_data": research_data,
        "query": query,
    })
