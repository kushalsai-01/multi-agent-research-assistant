from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from agents.schemas import AnalysisOutput
import config

SYSTEM_PROMPT = """You are a Senior Data Analyst. You receive raw research
findings and must produce a clear, structured analysis.

INSTRUCTIONS:
1. Read all the raw research data carefully.
2. Identify the TOP 5 most important findings with confidence scores (1-10).
3. Group related information into coherent themes/categories.
4. Highlight any statistics, numbers, or quantitative data.
5. Note contradictions or gaps in the research.
6. Assess the reliability of each source (high / medium / low).
7. Provide an overall confidence score (1-10) for the entire research.

For each key finding, include supporting source URLs where available.

Be analytical, not creative. Stick to what the data shows.
"""


def build_analyst_chain():
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0.2,
        api_key=config.GROQ_API_KEY,
    )
    structured_llm = llm.with_structured_output(AnalysisOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Raw research data:\n\n{research_data}\n\n"
                  "Original query: {query}\n\n"
                  "Produce your structured analysis now."),
    ])

    return prompt | structured_llm


def run_analyst(research_data: str, query: str) -> AnalysisOutput:
    """Run the analyst chain and return structured AnalysisOutput."""
    chain = build_analyst_chain()
    return chain.invoke({"research_data": research_data, "query": query})


def analyst_to_str(output: AnalysisOutput) -> str:
    """Convert structured AnalysisOutput to Markdown string for downstream agents."""
    lines = ["## Key Findings\n"]
    for i, kf in enumerate(output.key_findings, 1):
        sources_str = ", ".join(kf.sources) if kf.sources else "no direct source"
        lines.append(f"{i}. {kf.finding} (confidence: {kf.confidence}/10)")
        lines.append(f"   Sources: {sources_str}\n")

    lines.append("\n## Thematic Analysis\n")
    lines.append(output.thematic_analysis)

    lines.append("\n\n## Data & Statistics\n")
    lines.append(output.data_and_statistics)

    lines.append("\n\n## Gaps & Contradictions\n")
    lines.append(output.gaps_and_contradictions)

    lines.append("\n\n## Source Reliability Assessment\n")
    lines.append(output.source_reliability)

    lines.append(f"\n\nOverall Confidence: {output.overall_confidence}/10")

    return "\n".join(lines)
