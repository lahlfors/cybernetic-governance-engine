import logging
from typing import Any, List, Optional

from src.gateway.governance.singletons import symbolic_governor
from src.gateway.governance.nemo.vllm_client import VLLMLLM
from langchain_core.messages import HumanMessage

logger = logging.getLogger("NeMo.Actions")

async def check_approval_token(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates that an approval token is present (SC-1).
    Fail Closed: Returns False if token is missing.
    """
    token = context.get("approval_token")
    # STPAValidator SC-1 checks if token is not None
    violations = symbolic_governor.stpa_validator.validate("execute_trade", {"approval_token": token})

    if violations:
        logger.warning(f"🛡️ NeMo Action BLOCKED: check_approval_token - {violations}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: check_approval_token")
    return True

async def check_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates latency (SC-2/FIN-2). Alias for check_data_latency.
    """
    return await check_data_latency(context, event)

async def check_data_latency(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates market data latency (FIN-2).
    Fail Closed: Returns False if latency is unknown or high.
    """
    latency = context.get("latency_ms")
    if latency is None:
        logger.warning("🛡️ NeMo Action BLOCKED: check_data_latency - Latency unknown (Fail Closed)")
        return False

    violations = symbolic_governor.stpa_validator.validate("execute_trade", {"latency_ms": latency})

    if violations:
        logger.warning(f"🛡️ NeMo Action BLOCKED: check_data_latency - {violations}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: check_data_latency")
    return True

async def check_drawdown_limit(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates daily drawdown limit (UCA-5).
    Checks if system is healthy enough to trade.
    """
    amount = context.get("amount", 0.0)
    # CBF Check via SafetyFilter
    result = symbolic_governor.safety_filter.verify_action("execute_trade", {"amount": amount})

    if result.startswith("UNSAFE"):
        logger.warning(f"🛡️ NeMo Action BLOCKED: check_drawdown_limit - {result}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: check_drawdown_limit")
    return True

async def check_slippage_risk(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates slippage risk (UCA-6).
    """
    amount = context.get("amount", 0.0)
    # SafetyFilter handles both Drawdown and Slippage
    result = symbolic_governor.safety_filter.verify_action("execute_trade", {"amount": amount})

    if result.startswith("UNSAFE"):
        logger.warning(f"🛡️ NeMo Action BLOCKED: check_slippage_risk - {result}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: check_slippage_risk")
    return True

async def check_atomic_execution(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates atomic execution capabilities.
    Fail Closed: Currently not implemented in logic layer, so we block multi-leg trades.
    """
    logger.warning("🛡️ NeMo Action BLOCKED: check_atomic_execution - Multi-leg execution not supported yet (Fail Closed).")
    return False

async def invoke_vllm_fallback(context: dict = {}, events: list = [], content: str = None, **kwargs) -> str:
    """
    Action to call vLLM directly for fallback responses.
    Renamed from perform_vllm_fallback (fixed16/17).
    Flexible signature to handle NeMo context/events injection.
    """
    # Extract content if passed via kwargs or context if primary arg is None
    if content is None:
        content = kwargs.get("content")

    print(f"DEBUG: invoke_vllm_fallback CALLED with content='{content}', kwargs={kwargs.keys()}")

    try:
        if not content:
            print("DEBUG: invoke_vllm_fallback returning default due to empty content")
            return "I apologize, but I didn't catch that."

        logger.info(f"DEBUG: Executing invoke_vllm_fallback with content='{content}'")

        # Instantiate VLLM Client
        llm = VLLMLLM()

        # Create a simple message list
        messages = [HumanMessage(content=content)]

        # Call LLM
        response = await llm._acall(messages)

        print(f"DEBUG: invoke_vllm_fallback returning response length={len(response)}")
        return response

    except Exception as e:
        logger.error(f"❌ invoke_vllm_fallback failed: {e}")
        print(f"DEBUG: invoke_vllm_fallback EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return "I apologize, but I encountered an error generating a response."
