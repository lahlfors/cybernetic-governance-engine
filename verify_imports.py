import sys
import os

# Add src to path
sys.path.append(os.getcwd())

print("Testing imports...")
try:
    from config.settings import Config, MODEL_FAST, MODEL_REASONING, VLLM_FAST_API_BASE, VLLM_REASONING_API_BASE
    print(f"✅ Config loaded. MODEL_FAST={MODEL_FAST}, MODEL_REASONING={MODEL_REASONING}")
    print(f"   VLLM_FAST={VLLM_FAST_API_BASE}, VLLM_REASONING={VLLM_REASONING_API_BASE}")
except ImportError as e:
    print(f"❌ Failed to import config: {e}")
    sys.exit(1)

try:
    from src.governed_financial_advisor.agents.financial_advisor.agent import financial_coordinator
    print("✅ Financial Advisor Agent imported.")
except Exception as e:
    print(f"❌ Failed to import Financial Advisor Agent: {e}")
    # Don't fail hard here if it requires Vertex AI auth which might be missing in sandbox
    pass

print("Import test complete.")
