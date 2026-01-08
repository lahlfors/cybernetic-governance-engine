from google.adk.types import ModelClient
from google.adk.agents import LlmAgent
from google.genai.types import FunctionDeclaration, Tool, Schema

# ...
from financial_advisor.sub_agents.memory.schema import UserProfile
from financial_advisor.sub_agents.memory.prompt import get_memory_instruction

def update_user_profile(
    risk_tolerance: str,
    investment_horizon: str,
    investment_goals: list[str],
    preferred_sectors: list[str],
    disallowed_sectors: list[str],
    liquidity_needs: str,
    last_updated_summary: str
):
    """
    Updates the structural User Profile.
    """
    return "Profile Updated"

# Define the Tool for the Agent
profile_tool = Tool(
    function_declarations=[
        FunctionDeclaration(
            name="update_user_profile",
            description="Updates the persistent user profile with new traits.",
            parameters=Schema(
                type="OBJECT",
                properties={
                    "risk_tolerance": Schema(
                        type="STRING", 
                        enum=["Conservative", "Moderate", "Aggressive", "Unknown"]
                    ),
                    "investment_horizon": Schema(
                        type="STRING", 
                        enum=["Short Term", "Medium Term", "Long Term", "Unknown"]
                    ),
                    "investment_goals": Schema(
                        type="ARRAY", 
                        items=Schema(type="STRING")
                    ),
                    "preferred_sectors": Schema(
                        type="ARRAY", 
                        items=Schema(type="STRING")
                    ),
                    "disallowed_sectors": Schema(
                        type="ARRAY", 
                        items=Schema(type="STRING")
                    ),
                    "liquidity_needs": Schema(
                        type="STRING", 
                        enum=["High", "Medium", "Low", "Unknown"]
                    ),
                    "last_updated_summary": Schema(
                        type="STRING", 
                        description="Concise summary of changes"
                    )
                },
                required=["risk_tolerance", "last_updated_summary"]
            )
        )
    ]
)

# Initialize the Agent
def create_memory_agent(model_client):
    return LlmAgent(
        name="memory_manager",
        model_client=model_client,
        instruction=get_memory_instruction(),
        tools=[profile_tool]
    )
