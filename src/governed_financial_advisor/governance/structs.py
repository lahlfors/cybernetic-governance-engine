from pydantic import BaseModel, Field

class ConstraintLogic(BaseModel):
    """Structured logic for the transpiler"""
    variable: str = Field(description="The variable to check (e.g., 'order_size', 'drawdown', 'latency')")
    operator: str = Field(description="Comparison operator (e.g., '<', '>', '==')")
    threshold: str = Field(description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
    condition: str | None = Field(description="Pre-condition (e.g., 'order_type == MARKET')")

class ProposedUCA(BaseModel):
    """
    Proposed Unsafe Control Action identified by Risk Analysis.
    Used by PolicyTranspiler.
    """
    category: str = Field(description="STPA Category: Unsafe Action, Wrong Timing, Not Provided, Stopped Too Soon")
    hazard: str = Field(description="The specific financial hazard (e.g., 'H-4: Slippage > 1%')")
    description: str = Field(description="Description of the unsafe control action")
    constraint_logic: ConstraintLogic = Field(description="Structured logic for the transpiler")
