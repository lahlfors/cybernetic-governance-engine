from typing import List, Literal
from pydantic import BaseModel, Field

class RiskAssessment(BaseModel):
    risk_score: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(description="Overall risk score")
    primary_risk_factor: Literal["Volatility", "Liquidity", "Counterparty", "Operational", "Model", "Psychological"] = Field(description="Primary driver of risk")
    verdict: Literal["APPROVE", "REJECT"] = Field(description="Final decision")
    reasoning_summary: str = Field(description="Concise summary of why the verdict was reached")
    detected_unsafe_actions: List[str] = Field(description="List of specific unsafe control actions identified", default_factory=list)
    detailed_analysis_report: str = Field(description="The full detailed text report including Executive Summary, Market Risks, etc.")
