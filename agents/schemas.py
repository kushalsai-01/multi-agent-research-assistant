"""
Pydantic v2 structured output schemas for all agents.
Used with `.with_structured_output()` on LangChain chat models.
"""
from pydantic import BaseModel, Field
from typing import List


class KeyFinding(BaseModel):
    finding: str = Field(description="The key finding")
    confidence: int = Field(description="Confidence score 1-10")
    sources: List[str] = Field(default_factory=list, description="Supporting source URLs")


class AnalysisOutput(BaseModel):
    key_findings: List[KeyFinding] = Field(description="Top 5 key findings with confidence scores")
    thematic_analysis: str = Field(description="Grouped thematic insights in markdown")
    data_and_statistics: str = Field(description="All numbers, percentages, dates found")
    gaps_and_contradictions: str = Field(description="Missing info or conflicting data")
    source_reliability: str = Field(description="Reliability assessment per source")
    overall_confidence: int = Field(description="Overall research confidence 1-10")


class WriterSection(BaseModel):
    heading: str = Field(description="Section heading text")
    content: str = Field(description="Section content in markdown")


class WriterOutput(BaseModel):
    title: str = Field(description="Report title without # prefix")
    executive_summary: str = Field(description="3-4 sentence executive summary")
    sections: List[WriterSection] = Field(description="Report body sections")
    key_takeaways: List[str] = Field(description="3-5 bullet point takeaways")
    sources: List[str] = Field(description="All source URLs referenced")
    word_count: int = Field(description="Approximate word count of the report body")


class ReviewerOutput(BaseModel):
    quality_score: int = Field(description="Overall quality score 1-10")
    passed: bool = Field(description="True if score >= 7, report is publication-ready")
    polished_report: str = Field(description="The full polished report in Markdown, starting with # title")
    revision_instructions: str = Field(description="If passed=False, specific instructions for the writer to improve. Empty string if passed=True.")
    strengths: List[str] = Field(description="2-3 strengths of the current report")
    weaknesses: List[str] = Field(description="2-3 weaknesses to fix, empty list if passed=True")
