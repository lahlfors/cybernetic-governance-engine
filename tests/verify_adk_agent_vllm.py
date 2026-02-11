
import asyncio
import os
import logging
from src.governed_financial_advisor.infrastructure.llm.config import get_adk_model
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestADK")

# Set env vars for vLLM
os.environ["VLLM_BASE_URL"] = "http://localhost:8000/v1"
os.environ["VLLM_API_KEY"] = "EMPTY"
os.environ["GUARDRAILS_MODEL_NAME"] = "meta-llama/Meta-Llama-3.1-8B-Instruct"

async def main():
    logger.info("🧪 Testing ADK Agent with vLLM via Runner...")
    
    # 1. Create Model
    try:
        model = get_adk_model()
        logger.info(f"✅ Created LiteLlm model wrapper: {model}")
    except Exception as e:
        logger.error(f"❌ Failed to create model: {e}")
        return

    # 2. Create Agent
    try:
        agent = Agent(
            model=model,
            name="test_agent",
            instruction="You are a helpful assistant. Respond with 'PONG' if you receive 'PING'.",
        )
        logger.info("✅ Created ADK Agent")
    except Exception as e:
        logger.error(f"❌ Failed to create agent: {e}")
        return

    # 3. Create Runner
    try:
        session_service = InMemorySessionService()
        # Pre-create session
        await session_service.create_session(
            app_name="financial_advisor",
            user_id="test_user",
            session_id="test_session"
        )

        runner = Runner(
            agent=agent,
            session_service=session_service,
            app_name="financial_advisor"
        )
        logger.info("✅ Created Runner with InMemorySessionService")
    except Exception as e:
        logger.error(f"❌ Failed to create Runner: {e}")
        return

    # 4. Invoke Runner
    try:
        user_msg = "PING"
        logger.info(f"📤 Sending: {user_msg}")
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=user_msg)]
        )

        logger.info("Running runner.run()...")
        response_text = ""
        # Using run_async as run might be synchronous or async depending on implementation
        # adapters.py used runner.run() in a sync loop with nest_asyncio?
        # Let's check adapters.py again. It used:
        # for event in runner.run(user_id=user_id, session_id=session_id, new_message=new_message):
        # which implies run is a generator (sync).
        # But here run_async is safer for asyncio context?
        # If adapters.py uses sync run, it might block.
        # But let's try run() first if run_async fails or vice-versa.
        # ADK runners usually expose run() as generator and run_async() as async generator.
        
        async for event in runner.run_async(
            user_id="test_user",
            session_id="test_session",
            new_message=new_message
        ):
             if hasattr(event, 'content') and event.content:
                 for part in event.content.parts:
                     if hasattr(part, 'text') and part.text:
                         response_text += part.text
        
        logger.info(f"📝 Response content: {response_text}")
        
        if "PONG" in response_text.upper():
             logger.info("✅ SUCCESS: Agent replied with PONG")
        else:
             logger.warning("⚠️  WARNING: Agent did not reply with PONG.")
             
    except Exception as e:
        logger.error(f"❌ Runner execution failed: {e}")
        # import traceback
        # traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
