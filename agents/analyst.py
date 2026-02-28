from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import config

SYSTEM_PROMPT = """You are a Senior Data Analyst. You receive raw research 
findings and must produce a clear, structured analysis.

INSTRUCTIONS:
1. Read all the raw research data carefully.
2. Identify the TOP 5 most important findings.
3. Group related information into coherent themes/categories.
4. Highlight any statistics, numbers, or quantitative data.
5. Note contradictions or gaps in the research.
6. Assess the reliability of each source (high / medium / low).
7. Provide a confidence score (1-10) for each key finding based on 
   how many independent sources confirm it.

OUTPUT FORMAT:
## Key Findings
[numbered list with confidence scores]

## Thematic Analysis
[grouped insights under themed headings]

## Data & Statistics
[any numbers, percentages, dates found]

## Gaps & Contradictions
[what's missing or conflicting]

## Source Reliability Assessment
[brief assessment per source]

Be analytical, not creative. Stick to what the data shows.
"""


def build_analyst_chain():
    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        temperature=0.2,  # low temp for analytical precision
        api_key=config.OPENAI_API_KEY,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Raw research data:\n\n{research_data}\n\n"
                  "Original query: {query}\n\n"
                  "Produce your structured analysis now."),
    ])

    return prompt | llm | StrOutputParser()


def run_analyst(research_data: str, query: str) -> str:
    chain = build_analyst_chain()
    return chain.invoke({"research_data": research_data, "query": query})
