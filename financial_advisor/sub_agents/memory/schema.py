from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    """
    Structured representation of the User's financial profile and constraints.
    Persisted in Vertex AI Memory Bank.
    """
    risk_tolerance: Literal["Conservative", "Moderate", "Aggressive", "Unknown"] = Field(
        default="Unknown",
        description="The user's appetite for financial risk and volatility."
    )
    investment_horizon: Literal["Short Term", "Medium Term", "Long Term", "Unknown"] = Field(
        default="Unknown",
        description="The planned duration for holding investments."
    )
    investment_goals: List[str] = Field(
        default_factory=list,
        description="Specific financial goals (e.g., 'Retirement', 'Down payment', 'Speculation')."
    )
    preferred_sectors: List[str] = Field(
        default_factory=list,
        description="Sectors or industries the user has expressed interest in."
    )
    disallowed_sectors: List[str] = Field(
        default_factory=list,
        description="Sectors the user explicitly wants to avoid (e.g., ESG constraints)."
    )
    liquidity_needs: Literal["High", "Medium", "Low", "Unknown"] = Field(
        default="Unknown",
        description="How quickly the user needs to convert assets to cash."
    )
    last_updated_summary: str = Field(
        default="",
        description="A concise natural language summary of the user's latest context."
    )
