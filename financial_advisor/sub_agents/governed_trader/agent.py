from google.adk.agents import SequentialAgent

from .verifier import verifier_agent
from .worker import worker_agent

governed_trading_agent = SequentialAgent(
    name="governed_trading_agent",
    description=(
        "A governed trading pipeline that first proposes strategies (Worker) "
        "and then verifies them against security and semantic rules (Verifier)."
    ),
    sub_agents=[worker_agent, verifier_agent],
)
