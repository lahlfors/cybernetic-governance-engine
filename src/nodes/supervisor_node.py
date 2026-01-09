from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from config.settings import Config

class RouteDecision(BaseModel):
    # Map intents to your EXISTING agents
    next: Literal["data_analyst", "risk_analyst", "execution_analyst", "governed_trader", "human_review", "FINISH"]

def supervisor_node(state):
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("default"))
    structured_llm = llm.with_structured_output(RouteDecision)
    decision = structured_llm.invoke(state["messages"][-1])
    return {"next_step": decision.next}
