import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set env vars for vLLM
os.environ["VLLM_BASE_URL"] = "http://localhost:8000/v1"
os.environ["VLLM_API_KEY"] = "EMPTY"
os.environ["GUARDRAILS_MODEL_NAME"] = "meta-llama/Meta-Llama-3.1-8B-Instruct"

from src.governed_financial_advisor.utils.nemo_manager import create_nemo_manager, validate_with_nemo, VLLMLLM

async def main():
    print("🚀 Initializing NeMo Manager with vLLM config...")
    try:
        rails = create_nemo_manager()
    except Exception as e:
        print(f"❌ Failed to create rails: {e}")
        return

    prompt = "Hello, who are you?"
    print(f"🧪 Testing prompt: '{prompt}'")
    
    if rails.llm:
        print(f"DEBUG: rails.llm type: {type(rails.llm)}")
    else:
        print("DEBUG: rails.llm is None")

    try:
        is_safe, response = await validate_with_nemo(prompt, rails)
        
        print(f"✅ Result: is_safe={is_safe}")
        print(f"📝 Response: {response}")
        
    except Exception as e:
        print(f"❌ Execution failed: {e}")

    print("\n🔬 Verifying VLLMLLM class directly...")
    try:
        llm_instance = VLLMLLM()
        print(f"Testing _acall on {llm_instance}...")
        resp = await llm_instance._acall(prompt)
        print(f"VLLMLLM Response: '{resp}'")
    except Exception as e:
        print(f"❌ VLLMLLM direct call failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
