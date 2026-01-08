from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from financial_advisor.config import Config

class RouteDecision(BaseModel):
    next: Literal["market_worker", "human_review", "FINISH"] = Field(
        ..., description="Route based on user intent. Use 'market_worker' for analysis or trading. Use 'human_review' if the user explicitly asks for a human or escalation. Use 'FINISH' if the conversation is over."
    )

def supervisor_node(state):
    # Uses 'gemini-2.5-flash' for low-latency routing
    llm = ChatGoogleGenerativeAI(**Config.get_llm_config("default"))
    structured_llm = llm.with_structured_output(RouteDecision)

    last_message = state["messages"][-1]
    if isinstance(last_message, tuple):
        content = last_message[1]
    else:
        content = last_message.content

    # Decisions are strictly bound to the Schema
    decision = structured_llm.invoke(content)
    return {"next_step": decision.next}
