import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

def verify_agents():
    logger.info("Starting strict verification of PROMPT modules...")
    
    # 1. Memory Agent
    try:
        logger.info("Verifying Memory Infrastructure...")
        from financial_advisor.infrastructure.vertex_memory import get_memory_service
        logger.info("✅ Memory Infrastructure verified.")
    except Exception as e:
        logger.error(f"❌ Failed Memory Infrastructure: {e}")
        return False

    try:
        logger.info("Verifying Memory Agent Prompt...")
        from financial_advisor.sub_agents.memory import prompt as memory_prompt
        inst = memory_prompt.get_memory_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Memory Agent Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Memory Agent Prompt: {e}")
        return False

    # 2. Financial Coordinator
    try:
        logger.info("Verifying Financial Coordinator Prompt...")
        from financial_advisor import prompt as fc_prompt
        inst = fc_prompt.get_financial_coordinator_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Financial Coordinator Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Financial Coordinator Prompt: {e}")
        return False

    # 3. Governed Trader (Worker)
    try:
        logger.info("Verifying Governed Trader Prompt...")
        from financial_advisor.sub_agents.governed_trader import prompt as gt_prompt
        inst = gt_prompt.get_trading_analyst_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Governed Trader Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Governed Trader Prompt: {e}")
        return False

    # 4. Verifier
    try:
        logger.info("Verifying Verifier Prompt...")
        from financial_advisor.sub_agents.governed_trader import verifier_prompt
        inst = verifier_prompt.get_verifier_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Verifier Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Verifier Prompt: {e}")
        return False

    # 5. Data Analyst
    try:
        logger.info("Verifying Data Analyst Prompt...")
        from financial_advisor.sub_agents.data_analyst import prompt as da_prompt
        inst = da_prompt.get_data_analyst_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Data Analyst Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Data Analyst Prompt: {e}")
        return False

    # 6. Execution Analyst
    try:
        logger.info("Verifying Execution Analyst Prompt...")
        from financial_advisor.sub_agents.execution_analyst import prompt as ea_prompt
        inst = ea_prompt.get_execution_analyst_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Execution Analyst Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Execution Analyst Prompt: {e}")
        return False

    # 7. Risk Analyst
    try:
        logger.info("Verifying Risk Analyst Prompt...")
        from financial_advisor.sub_agents.risk_analyst import prompt as ra_prompt
        inst = ra_prompt.get_risk_analyst_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Risk Analyst Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Risk Analyst Prompt: {e}")
        return False

    # 8. Trading Analyst
    try:
        logger.info("Verifying Trading Analyst Prompt...")
        from financial_advisor.sub_agents.trading_analyst import prompt as ta_prompt
        inst = ta_prompt.get_trading_analyst_instruction()
        if not isinstance(inst, str) or len(inst) < 10:
             raise ValueError("Instruction is not a valid string")
        logger.info("✅ Trading Analyst Prompt verified.")
    except Exception as e:
        logger.error(f"❌ Failed Trading Analyst Prompt: {e}")
        return False

    logger.info("🎉 All PROMPTS verified successfully!")
    return True

if __name__ == "__main__":
    if verify_agents():
        sys.exit(0)
    else:
        sys.exit(1)
