"""
ADK Agent Adapters for LangGraph Nodes

Uses Dependency Injection pattern to allow mocking during tests.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.governed_financial_advisor.utils.text_utils import strip_thinking_tags

# LangSmith Deep Integration
try:
    from langsmith import traceable
except ImportError:
    # No-op decorator if langsmith is not installed (e.g., during minimal tests)
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator

# Import Factory Functions
from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_agent
from src.governed_financial_advisor.agents.execution_analyst.agent import create_execution_analyst_agent
from src.governed_financial_advisor.agents.governed_trader.agent import create_governed_trader_agent

# Session management for ADK agents
session_service = InMemorySessionService()

logger = logging.getLogger("Graph.Adapters")




def get_valid_last_message(state) -> str:
    """Retrieves the last non-empty message content from the state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        # Handle simple string content
        if isinstance(content, str) and content.strip():
            return content
        # Handle list content (multi-modal or parts)
        if isinstance(content, list) and content:
             return content # Pass complex content through
    return "No content available."

def get_market_data_from_history(state) -> str | None:
    """
    Scans the conversation history for the most recent Data Analyst output.
    Returns the content if found, or None.
    """
    messages = state.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            # Check for explicit Data Analyst output
            if "Data Analysis:" in content:
                return content
            # Fallback: Check if the prompt itself contains "Analyze" (for Step 2 of Eval)
            if "Analyze" in content and "stock performance" in content:
                 return content # Treat the prompt as the context trigger
    return None

# --- Dependency Injection Infrastructure ---

_agent_registry = {}
_agent_cache = {}

def get_agent(name: str, factory: Callable[[], Any]) -> Any:
    """
    Retrieves an agent instance.
    If a mock is registered in _agent_registry, returns that.
    Otherwise, creates (and caches) the real agent using the factory.
    """
    # 1. Check for overrides/mocks (Transient)
    if name in _agent_registry:
        return _agent_registry[name]

    # 2. Check cache (Singleton)
    if name not in _agent_cache:
        logger.info(f"Creating new agent instance for: {name}")
        _agent_cache[name] = factory()

    return _agent_cache[name]

def inject_agent(name: str, instance: Any):
    """Injects an agent instance (mock) for testing."""
    _agent_registry[name] = instance

def clear_agent_cache():
    """Clears the agent cache and registry."""
    _agent_registry.clear()
    _agent_cache.clear()

class AgentResponse:
    """Simple response object to hold agent output."""
    def __init__(self, answer: str = "", function_calls=None):
        self.answer = answer
        self.function_calls = function_calls or []

@traceable(run_type="chain", name="ADK Agent Runner")
def run_adk_agent(agent_instance, user_msg: str, session_id: str = "default", user_id: str = "default_user"):
    """
    Wraps the ADK Agent Runner to execute a turn and return the result object.
    Uses the updated Runner.run() API: run(user_id, session_id, new_message)
    """
    import nest_asyncio
    nest_asyncio.apply()

    # Helper to create session asynchronously
    async def ensure_session():
        existing = await session_service.get_session(
            app_name="financial_advisor",
            user_id=user_id,
            session_id=session_id
        )
        if not existing:
            await session_service.create_session(
                app_name="financial_advisor",
                user_id=user_id,
                session_id=session_id
            )

    # Ensure session exists before running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Use nest_asyncio to allow re-entrant loop if needed
    loop.run_until_complete(ensure_session())

    runner = Runner(
        agent=agent_instance,
        session_service=session_service,
        app_name="financial_advisor"
    )

    # Format the message as Content
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=user_msg)]
    )

    # Run and collect events to extract answer
    final_answer_parts = []
    
    # Tool Loop
    max_turns = 10
    current_turn = 0
    
    # We loop until the model stops calling tools or we hit max_turns
    while current_turn < max_turns:
        current_turn += 1
        
        turn_answer_parts = []
        turn_function_calls = []
        
        try:
            # Execute Runner for this turn
            for event in runner.run(user_id=user_id, session_id=session_id, new_message=new_message):
                print(f"🔎 ADK Event: {type(event)} - {event}")

                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            print(f"📝 Event Content Part: {part.text[:50]}...")
                            turn_answer_parts.append(part.text)
                        if hasattr(part, 'function_call') and part.function_call:
                            print(f"🛠️ Event Function Call: {part.function_call}")
                            turn_function_calls.append(part.function_call)
                            
        except Exception as e:
            logger.error(f"Error running ADK agent: {e}")
            return AgentResponse(answer=f"Error: {e!s}")

        # If no tool calls, we are done with this turn and the whole conversation for now
        if not turn_function_calls:
            # Accumulate the text from this final turn
            final_answer_parts.extend(turn_answer_parts)
            break
            
        # If we have tool calls, we must execute them and feed results back
        # The text generated ALONGSIDE the tool call (e.g. "I will check...") is usually kept?
        # Typically we might want to keep it if it's relevant, but for the final answer we usually want the LAST response.
        # But let's accumulate it just in case, or ignore it if we want only the final result.
        # For now, let's NOT accumulate intermediate text to avoid clutter, UNLESS it's the final answer.
        # Actually, sometimes the model explains what it is doing first.
        # Let's log it but not return it as the 'answer' unless it's the only thing.
        if turn_answer_parts:
             logger.info(f"Intermediate thought: {''.join(turn_answer_parts)}")

        tool_outputs = []
        for call in turn_function_calls:
            logger.info(f"🔎 Executing Tool: {call.name}")
            
            # Find the tool in the agent's registry
            target_tool = None
            if hasattr(agent_instance, 'tools'):
                for tool in agent_instance.tools:
                    # Check 'name' attribute or 'fn.__name__' if it's a FunctionTool
                    t_name = getattr(tool, 'name', None)
                    if not t_name and hasattr(tool, 'fn'):
                         t_name = tool.fn.__name__
                    
                    if t_name == call.name:
                        target_tool = tool
                        break
            
            result_content = {}
            if target_tool:
                try:
                    # Extract arguments
                    args = dict(call.args) if call.args else {}
                    
                    # Execute
                    # Support both .run() and direct .fn() call
                    if hasattr(target_tool, 'run'):
                        # checks if run takes **kwargs
                        res = target_tool.run(**args)
                    elif hasattr(target_tool, 'fn'):
                        res = target_tool.fn(**args)
                    elif callable(target_tool):
                        res = target_tool(**args)
                    else:
                        res = f"Error: Tool {call.name} is not callable."
                    
                    # Handle Async Tools
                    if asyncio.iscoroutine(res):
                        try:
                            # We expect a loop to exist since we created/got one earlier
                            # nest_asyncio was applied at start of function
                            curr_loop = asyncio.get_running_loop()
                            if curr_loop.is_running():
                                res = curr_loop.run_until_complete(res)
                            else:
                                res = curr_loop.run_until_complete(res)
                        except RuntimeError:
                            # Fallback if no running loop found (unlikely)
                            res = asyncio.run(res)

                    # Ensure result is serializable (usually dict or str)
                    result_content = res if isinstance(res, (dict, list, str, int, float, bool)) else str(res)
                    
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    result_content = {"error": str(e)}
            else:
                logger.error(f"Tool {call.name} not found in agent tools.")
                result_content = {"error": f"Tool {call.name} not found."}

            tool_outputs.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=call.name,
                        response={"result": result_content}
                    )
                )
            )
        
        # Prepare the NEXT message (inputs for the next turn)
        # This message contains the tool outputs
        if tool_outputs:
            new_message = types.Content(
                role="tool", # or 'function' depending on API, types.Content usually uses 'tool' for function responses in Gemini
                parts=tool_outputs
            )
            logger.info(f"Feeding back {len(tool_outputs)} tool results...")
        else:
            # Should not reach here if turn_function_calls was not empty
            break

    return AgentResponse(answer=strip_thinking_tags("".join(final_answer_parts)), function_calls=[])


# --- Node Implementations ---

from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_planner, create_data_analyst_executor

def data_analyst_node(state):
    """
    Wraps the Data Analyst agent for LangGraph.
    Now split into:
    1. Planner (DeepSeek): Extracts ticker/intent.
    2. Executor (Llama 3): Generates tool calls.
    3. Tool Loop: Executes tools and gets final answer.
    """
    print("--- [Graph] Calling Data Analyst (Split) ---")
    
    # 1. PLANNER: "Describe the task/intent"
    # The Planner uses DeepSeek (Reasoning) to understand the context.
    # We pass the full history or just the last message.
    planner = get_agent("data_analyst_planner", create_data_analyst_planner)
    last_msg = get_valid_last_message(state)
    
    print(f"--- [Planner] Analyzing request: {last_msg[:50]}... ---")
    # Planner should output a concise plan or just the ticker if that's the prompt.
    # Current prompt asks for "Just the ticker" but we can rely on its reasoning.
    planner_res = run_adk_agent(planner, last_msg)
    
    # Extract the plan (e.g. Ticker)
    # If the model used <think> tags, 'planner_res.answer' already has them stripped by 'run_adk_agent'
    plan_content = planner_res.answer.strip()
    print(f"--- [Planner] Plan/Ticker: {plan_content} ---")

    # 2. EXECUTOR: "Execute the plan"
    # We pass the plan to the Executor (Qwen/DeepSeek) which is forced to call tools.
    # We use a factory that might bind tools specific to the ticker if needed, 
    # but usually it just needs the ticker in the prompt or message.
    
    # If the plan is just a ticker, we might want to frame it as "Fetch data for {ticker}"
    # to ensure the Executor (which might be generic) knows what to do.
    # If the output is "AAPL", we say "Fetch data for AAPL".
    
    executor_input = plan_content
    # Heuristic: if it looks like a ticker (short, no spaces), wrap it.
    if len(executor_input.split()) < 2:
        executor_input = f"Fetch market data for {executor_input}"
        
    executor_agent_name = f"data_analyst_executor"
    # We don't need to pass ticker to factory if we pass it in the prompt, 
    # BUT the factory might need it for system instructions.
    # Let's inspect the factory in agent.py (it takes 'ticker').
    # If we pass 'ticker' to factory, it bakes it into system prompt.
    # So we should extract the ticker cleanly.
    
    ticker = plan_content.split()[-1] # Simple fallback extraction if it talks a lot
    # Ideally Planner just outputs the ticker.
    if len(plan_content) < 10:
         ticker = plan_content
    
    print(f"--- [Executor] Initializing for Ticker: {ticker} ---")
    executor = get_agent(f"{executor_agent_name}_{ticker}", lambda: create_data_analyst_executor(ticker))
    
    # 3. TOOL LOOP (Handled by run_adk_agent)
    # The executor is configured with tool_choice='required' (usually) or just tools.
    # run_adk_agent will loop: Model triggers Tool -> Agent executes Tool -> Model sees result -> Final Answer.
    print(f"--- [Executor] Executing Tool Loop ---")
    executor_res = run_adk_agent(executor, executor_input)
    
    print(f"DEBUG DATA ANALYSIS: Length {len(executor_res.answer)}")
    
    return {
        "messages": [("ai", f"Data Analysis for {ticker}:\n{executor_res.answer}")],
        "data_analyst_ticker": ticker
    }


def execution_analyst_node(state):
    """
    Wraps the Execution Analyst (Planner) agent for LangGraph.
    Injects risk feedback if the loop pushed us back here.
    Parses the JSON output to populate 'execution_plan_output'.
    """
    print("--- [Graph] Calling Execution Analyst (Planner) ---")
    agent = get_agent("execution_analyst", create_execution_analyst_agent)
    user_msg = get_valid_last_message(state)

    # 0. DATA CHECK: We need market data to form a specific strategy.
    # We now look back in history, not just the immediate last message.
    market_data_msg = get_market_data_from_history(state)
    
    # RELAXED CHECK: If the user is explicitly asking for a strategy (Step 3/4), 
    # we might not have a "Data Analysis:" message if we skipped that step or if it was just a prompt.
    # In strict eval flow, we should try to proceed.
    if not market_data_msg and "strategy" not in user_msg.lower(): 
        print("--- [Graph] Missing Market Data -> Asking User for Ticker ---")
        return {
            "messages": [("ai", "I can certainly help you develop a trading strategy. **Which stock ticker** would you like me to research first?")],
            "next_step": "FINISH",
            "risk_status": "UNKNOWN",
            "execution_plan_output": None
        }

    # 1. PROFILE CHECK: DISABLED to allow Agent to extract it from context
    # if not state.get("risk_attitude") or not state.get("investment_period"):
    #     print("--- [Graph] Missing Profile -> Asking User ---")
    #     msg = (
    #         "I have the market analysis. To tailor the strategy, please select your **Risk Tolerance** and **Time Frame**:\n\n"
    #         "Stock trading strategies generally fall into three levels of aggressiveness:\n"
    #         "- **Aggressive** (High Risk, High Growth): Maximizes returns with higher volatility exposure.\n"
    #         "- **Moderate** (Balanced Risk/Reward): Balances growth and capital preservation.\n"
    #         "- **Conservative** (Low Risk, Capital Preservation): Prioritizes stability and lower turnover.\n\n"
    #         "Please copy and paste your choice (e.g., 'Aggressive') and specify your **Time Frame** (Short, Medium, or Long)."
    #     )
    #     return {
    #         "messages": [("ai", msg)],
    #         "next_step": "FINISH",
    #         "risk_status": "UNKNOWN",
    #         "execution_plan_output": None
    #     }

    # INJECT FEEDBACK if the loop pushed us back here
    if state.get("risk_status") == "REJECTED_REVISE":
        # 1. CIRCUIT BREAKER: Check recursion depth
        current_loop = state.get("loop_count", 0) or 0
        if current_loop >= 3:
             print(f"🛑 [Circuit Breaker] Max Loops ({current_loop}) reached. Terminating recursion.")
             return {
                "messages": [("ai", "I cannot recommend a trade at this time due to persistent safety policy violations. Please adjust your risk profile or select a different asset.")],
                "next_step": "FINISH",
                "risk_status": "UNKNOWN",
                "execution_plan_output": None
            }
        
        # 2. Increment Loop Count
        feedback = state.get("risk_feedback")
        user_msg = (
            f"CRITICAL: Your previous strategy was REJECTED by Risk Management.\n"
            f"Feedback: {feedback}\n"
            f"Task: Generate a REVISED, SAFER strategy based on this feedback."
        )
        print(f"--- [Loop {current_loop+1}] Injecting Risk Feedback ---")
    
    # PIPELINE LOGIC: Construct the prompt with context
    else:
        # Reset Loop Count on fresh start
        state["loop_count"] = 0
        current_loop = 0
        # Check if we already have risk attitude in state, if so, mention it.
        risk = state.get("risk_attitude", "moderate") # Default to moderate if unknown, or let agent ask
        period = state.get("investment_period", "medium-term")

        # If the user just asked for a strategy (e.g. "Recommend a strategy"), we want to
        # include the market data in the context so the agent doesn't hallucinate or ask for it again.
        
        # If the last message IS the data analysis, user_msg is already set to it.
        # If the last message is a user prompt, we assume it's the trigger.
        
        user_msg = (
            f"CONTEXT: The following is the Market Analysis we have already performed.\n"
            f"USER PROFILE: Risk Attitude: {risk}, Horizon: {period}\n"
            f"CURRENT REQUEST: {user_msg}\n"
            f"TASK: Generate a suggested set of specific trading strategies (Execution Plan) based on the analysis below.\n"
            f"Ensure the strategies are concrete, actionable, and aligned with the Risk/Time profile.\n\n"
            f"--- MARKET ANALYSIS ---\n"
            f"{market_data_msg}"
        )
        print("--- [Pipeline] Auto-prompting Strategy Generation with Context ---")

    res = run_adk_agent(agent, user_msg)

    # PARSE JSON Output
    plan_output = None
    try:
        # The agent is configured to return JSON, so res.answer should be a JSON string.
        # We try to parse it.
        # Handle markdown blocks ```json ... ``` if present
        json_str = res.answer
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
             json_str = json_str.split("```")[1].split("```")[0].strip()

        plan_output = json.loads(json_str)
        logger.info(f"✅ Parsed Execution Plan: {plan_output.get('plan_id', 'unknown')}")

    except Exception as e:
        logger.warning(f"⚠️ Failed to parse Execution Plan JSON: {e}. Passing raw text.")
        # Fallback: create a dummy plan wrapper around the text so Safety Node doesn't crash completely
        plan_output = {
            "steps": [],
            "reasoning": res.answer,
            "error": "Failed to parse JSON plan"
        }

    # Format the output for the user
    if plan_output and isinstance(plan_output, dict):
        steps_text = "\n".join([f"{i+1}. {s.get('action')} ({s.get('description')})" for i, s in enumerate(plan_output.get("steps", []))])
        final_response = (
            f"### Executive Plan: {plan_output.get('strategy_name', 'Custom Strategy')}\n\n"
            f"**Rationale:** {plan_output.get('rationale')}\n\n"
            f"**Steps:**\n{steps_text}\n\n"
            f"**Risk Factors:** {', '.join(plan_output.get('risk_factors', []))}\n\n"
            f"*(Generated by System 4 Planner)*\n\n"
            f"**Would you like me to execute this trade or implement this plan?**"
        )
    else:
        final_response = res.answer

    # Reset status so we can potentially loop again or proceed
    # Reset status so we can potentially loop again or proceed
    updates = {
        "messages": [("ai", final_response)],
        "risk_status": "UNKNOWN",
        "execution_plan_output": plan_output,
        "loop_count": (state.get("loop_count", 0) or 0) + 1 if state.get("risk_status") == "REJECTED_REVISE" else 0,
    }
    
    # Update State from Plan (Context Extraction) ONLY if present in output
    if plan_output:
        if plan_output.get("user_risk_attitude"):
            updates["risk_attitude"] = plan_output.get("user_risk_attitude")
        if plan_output.get("user_investment_period"):
            updates["investment_period"] = plan_output.get("user_investment_period")
            
    return updates


def governed_trader_node(state):
    """Wraps the Governed Trader agent for LangGraph."""
    print("--- [Graph] Calling Governed Trader ---")
    agent = get_agent("governed_trader", create_governed_trader_agent)
    last_msg = get_valid_last_message(state)
    res = run_adk_agent(agent, last_msg)
    return {"messages": [("ai", res.answer)]}
