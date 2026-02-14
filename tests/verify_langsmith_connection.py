import os
import sys
import time
import logging
from dotenv import load_dotenv

# Load .env immediately
load_dotenv()

# Ensure src is in pythonpath
sys.path.append(os.getcwd())

from src.governed_financial_advisor.utils.telemetry import configure_telemetry, get_tracer
from opentelemetry import trace

# Configure logging to see our success messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LangSmithVerify")

def main():
    print("🚀 Starting LangSmith Connection Verification...")

    # 1. Force Sampling to 100% for this test
    os.environ["TRACE_SAMPLING_RATE"] = "1.0"

    # Check for API Key
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        print("⚠️ LANGSMITH_API_KEY not found in environment. Please set it in .env")
        # return # Proceed anyway to test the graceful degradation

    # 2. Configure Telemetry
    configure_telemetry()

    tracer = get_tracer()
    if not tracer:
        print("❌ Tracer not available!")
        return

    print("🔍 Creating Test Span...")
    try:
        with tracer.start_as_current_span("langsmith-connectivity-check") as span:
            span.set_attribute("test.id", "connectivity-check")
            span.set_attribute("gen_ai.usage.prompt_tokens", 10)
            span.set_attribute("gen_ai.usage.completion_tokens", 20)
            span.add_event("Processing started")
            time.sleep(0.5)
            span.add_event("Processing finished")
            print("✅ Span created and closed.")

    except Exception as e:
        print(f"❌ Error creating span: {e}")

    # 3. Force Flush
    # The tracer provider holds the processors. We need to access them to flush.
    print("⏳ Forcing Flush...")
    try:
        from opentelemetry.trace import get_tracer_provider
        provider = get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush()
            print("✅ Flush triggered.")
        else:
            print("⚠️ Provider does not have force_flush method.")

        # Also try shutdown to be sure
        if hasattr(provider, "shutdown"):
            provider.shutdown()
            print("✅ Provider shut down.")

    except Exception as e:
        print(f"❌ Error during flush: {e}")

    print("\nCheck LangSmith Dashboard for a span named 'langsmith-connectivity-check'.")

if __name__ == "__main__":
    main()
