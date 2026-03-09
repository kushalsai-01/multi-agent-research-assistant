from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import config

SYSTEM_PROMPT = """You are a Senior Editor. Your job is to review a research report and output an improved, publication-ready final version.

REVIEW PROCESS (do this internally, do not output the review):
1. Check accuracy — are all claims supported by the research data?
2. Check completeness — are all key aspects of the topic covered?
3. Check clarity — is the writing clear, well-structured, and professional?
4. Check sources — are URLs cited properly?
5. Fix any issues you find: improve weak sentences, fix structure, add missing context.

OUTPUT RULES — CRITICAL:
- Output ONLY the final polished report in Markdown format.
- Do NOT output a scorecard, table, review summary, strengths/weaknesses list, or verdict.
- Do NOT output any commentary about your changes.
- Do NOT output headings like "Final Report", "Quality Review", or "Verdict".
- Start directly with the report title (# heading) and end with the Sources section.
- The report must be between 800-1500 words.
- Keep the same Markdown structure as the original: title, executive summary blockquote, sections, key takeaways, sources.
"""


def build_reviewer_chain():
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0.2,
        api_key=config.GROQ_API_KEY,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Original topic: {query}\n\n"
                  "Research data available:\n{research_data}\n\n"
                  "Report to review and improve:\n{report}\n\n"
                  "Output only the final polished report. Start with the # title."),
    ])

    return prompt | llm | StrOutputParser()


def run_reviewer(report: str, research_data: str, query: str) -> str:
    chain = build_reviewer_chain()
    result = chain.invoke({
        "report": report,
        "research_data": research_data,
        "query": query,
    })
    # Safety: if LLM still prefixed with "Final Report" heading, strip it
    for prefix in ["## Final Report\n", "# Final Report\n", "Final Report\n"]:
        if result.strip().startswith(prefix):
            result = result.strip()[len(prefix):]
    return result.strip()

    })
