from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Enums for Traceability ---

class LossType(str, Enum):
    L1_LOSS_OF_LIFE = "L-1: Loss of life or injury"
    L2_ASSET_DAMAGE = "L-2: Loss of or damage to vehicle/asset"
    L3_ENV_DAMAGE = "L-3: Damage to objects outside the vehicle"
    L4_MISSION_LOSS = "L-4: Loss of mission"

class HazardType(str, Enum):
    H1_SEPARATION = "H-1: Violates minimum separation"
    H2_INTEGRITY = "H-2: Structural/Asset integrity lost"
    H3_TERRAIN = "H-3: Unsafe distance from terrain"
    # Financial Extensions
    H_FIN_INSOLVENCY = "H-FIN-1: Insolvency (Drawdown > Limit)"
    H_FIN_LIQUIDITY = "H-FIN-2: Liquidity Trap (Slippage)"
    H_FIN_AUTHORIZATION = "H-FIN-3: Unauthorized Trading"

class ComponentType(str, Enum):
    HUMAN_SUPERVISOR = "Human Supervisor"
    AI_CONTROLLER = "AI Controller"
    ACTUATOR = "Actuator"
    SENSOR = "Sensor"

class UCAType(str, Enum):
    NOT_PROVIDED = "Not Providing Causes Hazard"
    PROVIDED = "Providing Causes Hazard"
    TIMING_WRONG = "Too Early / Too Late"
    STOPPED_TOO_SOON = "Stopped Too Soon / Lasted Too Long"

# --- Models ---

class ControlLoop(BaseModel):
    """
    Metadata describing the STPA Control Loop context.
    Maps the abstract STPA model to the concrete LangGraph execution.
    """
    id: str = Field(..., description="Unique ID for this loop instance")
    name: str = Field(..., description="Name of the loop, e.g., 'Trading Execution Loop'")
    controller: str = Field(..., description="The AI Agent (e.g., 'ExecutionAnalyst')")
    controlled_process: str = Field(..., description="The external system (e.g., 'Market/Exchange')")
    control_actions: List[str] = Field(..., description="List of allowed actions (e.g., ['buy', 'sell'])")
    feedback_mechanism: str = Field(..., description="How the agent sees state (e.g., 'Market Data Feed')")

class ConstraintLogic(BaseModel):
    """
    Structured logic for the Transpiler to generate code.
    """
    variable: str = Field(..., description="The variable to check (e.g., 'order_size', 'drawdown')")
    operator: str = Field(..., description="Comparison operator (e.g., '<', '>', '==')")
    threshold: str = Field(..., description="Threshold value or reference (e.g., '0.01 * daily_volume', '200')")
    condition: Optional[str] = Field(None, description="Pre-condition (e.g., 'order_type == MARKET')")

class ProcessModelFlaw(BaseModel):
    """
    Represents a divergence between the Agent's belief and Reality (Causal Factor).
    """
    believed_state: str = Field(..., description="What the Agent thought (e.g., 'Market is Stable')")
    actual_state: str = Field(..., description="What was true (e.g., 'Flash Crash in progress')")
    missing_feedback: Optional[str] = Field(None, description="What sensor data was missing or misinterpreted?")

class UCA(BaseModel):
    """
    Unsafe Control Action (UCA) - The Core STPA Artifact.
    Unifies definitions across Risk Analyst (Discovery) and Evaluator (Red Team).
    """
    id: str = Field(..., description="Unique ID, e.g., 'UCA-1'")
    type: UCAType = Field(..., description="The STPA Failure Mode")
    hazard: HazardType = Field(..., description="The System-Level Hazard this action leads to")
    description: str = Field(..., description="Natural language description of the unsafe action")

    # Logic for the Transpiler (Optional for Red Team manual entries, required for Auto-Generated)
    logic: Optional[ConstraintLogic] = None

    # Causal Analysis (The "Why")
    process_model_flaw: Optional[ProcessModelFlaw] = None

    # Detection pattern for the Auditor/Red Team
    trace_pattern: Optional[str] = None
