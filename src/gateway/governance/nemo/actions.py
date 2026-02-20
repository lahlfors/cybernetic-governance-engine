import logging
from typing import Any

from src.gateway.governance.singletons import symbolic_governor

logger = logging.getLogger("NeMo.Actions")

async def CheckApprovalTokenAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates that an approval token is present (SC-1).
    Fail Closed: Returns False if token is missing.
    """
    token = context.get("approval_token")
    # STPAValidator SC-1 checks if token is not None
    violations = symbolic_governor.stpa_validator.validate("execute_trade", {"approval_token": token})

    if violations:
        logger.warning(f"🛡️ NeMo Action BLOCKED: CheckApprovalTokenAction - {violations}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: CheckApprovalTokenAction")
    return True

async def CheckLatencyAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates latency (SC-2/FIN-2). Alias for check_data_latency.
    """
    return await CheckDataLatencyAction(context, event)

async def CheckDataLatencyAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates market data latency (FIN-2).
    Fail Closed: Returns False if latency is unknown or high.
    """
    latency = context.get("latency_ms")
    if latency is None:
        logger.warning("🛡️ NeMo Action BLOCKED: CheckDataLatencyAction - Latency unknown (Fail Closed)")
        return False

    violations = symbolic_governor.stpa_validator.validate("execute_trade", {"latency_ms": latency})

    if violations:
        logger.warning(f"🛡️ NeMo Action BLOCKED: CheckDataLatencyAction - {violations}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: CheckDataLatencyAction")
    return True

async def CheckDrawdownLimitAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates daily drawdown limit (UCA-5).
    Checks if system is healthy enough to trade.
    """
    amount = context.get("amount", 0.0)
    # CBF Check via SafetyFilter
    result = symbolic_governor.safety_filter.verify_action("execute_trade", {"amount": amount})

    if result.startswith("UNSAFE"):
        logger.warning(f"🛡️ NeMo Action BLOCKED: CheckDrawdownLimitAction - {result}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: CheckDrawdownLimitAction")
    return True

async def CheckSlippageRiskAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates slippage risk (UCA-6).
    """
    amount = context.get("amount", 0.0)
    # SafetyFilter handles both Drawdown and Slippage
    result = symbolic_governor.safety_filter.verify_action("execute_trade", {"amount": amount})

    if result.startswith("UNSAFE"):
        logger.warning(f"🛡️ NeMo Action BLOCKED: CheckSlippageRiskAction - {result}")
        return False

    logger.debug("🛡️ NeMo Action PASSED: CheckSlippageRiskAction")
    return True

async def CheckAtomicExecutionAction(context: dict[str, Any] = {}, event: dict[str, Any] = {}) -> bool:
    """
    Validates atomic execution capabilities.
    Fail Closed: Currently not implemented in logic layer, so we block multi-leg trades.
    """
    logger.warning("🛡️ NeMo Action BLOCKED: CheckAtomicExecutionAction - Multi-leg execution not supported yet (Fail Closed).")
    return False

async def InvokeVllmFallbackAction(context: dict = {}, events: list = [], content: str = None, **kwargs) -> str:
    """
    Action to call vLLM directly for fallback responses.
    Accepts context/events to satisfy NeMo's potential automatic injection, plus explicit content.
    """
    print(f"DEBUG ACTION ARGS: context={context}, events={events}, content={content}, kwargs={kwargs}")
    # Handle case where content might be passed as positional or keyword, or missing
    # formatting content to be safe
    final_content = content or kwargs.get('content', "")
    
    logger.warning(f"🔔 InvokeVllmFallbackAction CALLED. content='{final_content}'")
    
    try:
        if not final_content:
            logger.warning("InvokeVllmFallbackAction returning default due to empty content")
            return "I apologize, but I didn't catch that."
            
        logger.info(f"DEBUG: Executing InvokeVllmFallbackAction with content='{final_content}'")
        
        # Restore actual VLLM call for fallback
        from src.gateway.governance.nemo.vllm_client import VLLMLLM
        from langchain_core.messages import HumanMessage

        llm = VLLMLLM()
        # Create a simple message list
        messages = [HumanMessage(content=final_content)]
        
        # Use _acall (or _agenerate) directly
        response = await llm._acall(messages)
        
        print(f"DEBUG: InvokeVllmFallbackAction returning response length={len(response)}")
        return response

    except Exception as e:
        logger.error(f"❌ InvokeVllmFallbackAction failed: {e}")
        print(f"DEBUG: InvokeVllmFallbackAction EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return "I apologize, but I encountered an error generating a response."
