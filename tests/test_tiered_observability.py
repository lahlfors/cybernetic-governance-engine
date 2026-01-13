import os
import shutil
import time
import pandas as pd
from unittest.mock import MagicMock, patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from src.infrastructure.telemetry.tiered_processor import TieredSpanProcessor

# Setup
COLD_TIER_DIR = "tests/temp_cold_tier"

def setup_telemetry():
    if os.path.exists(COLD_TIER_DIR):
        shutil.rmtree(COLD_TIER_DIR)

    provider = TracerProvider()
    # Do NOT set global provider to avoid state leakage
    # trace.set_tracer_provider(provider)

    # Tiered Processor
    tiered = TieredSpanProcessor(cold_tier_path=COLD_TIER_DIR)
    provider.add_span_processor(tiered)

    # Mock Hot Exporter via SimpleSpanProcessor
    hot_exporter = MagicMock()
    provider.add_span_processor(SimpleSpanProcessor(hot_exporter))

    return provider, hot_exporter, tiered

def test_read_sampling():
    """Test that READ (Chat) is sampled at 1% (simulated)."""
    provider, hot_exporter, tiered_processor = setup_telemetry()
    tracer = provider.get_tracer("test")

    # Force random to return 0.0 (sample)
    with patch("random.random", return_value=0.0):
        with tracer.start_as_current_span("chat_completion") as span:
            span.set_attribute("gen_ai.content.prompt", "Hello")
            span.set_attribute("gen_ai.content.completion", "Hi there")
            span.set_attribute("other.metadata", "123")

    # Verify Cold Tier
    files = list(pd.read_parquet(f"{COLD_TIER_DIR}/{f}") for f in os.listdir(COLD_TIER_DIR))
    assert len(files) == 1
    df = files[0]
    assert df["attr.gen_ai.content.prompt"].iloc[0] == "Hello"

    # Verify Hot Tier (Stripped)
    exported_spans = hot_exporter.export.call_args[0][0]
    exported_span = exported_spans[0]

    assert "gen_ai.content.prompt" not in exported_span.attributes
    assert "other.metadata" in exported_span.attributes

def test_write_sampling():
    """Test that WRITE (Tool) is sampled at 100%."""
    provider, hot_exporter, tiered_processor = setup_telemetry()
    tracer = provider.get_tracer("test")

    # Force random to return 0.99 (no sample by default)
    with patch("random.random", return_value=0.99):
        with tracer.start_as_current_span("execute_trade") as span:
            span.set_attribute("gen_ai.tool.name", "trade_tool")
            span.set_attribute("gen_ai.content.prompt", "Buy AAPL")

    # Verify Cold Tier
    assert len(os.listdir(COLD_TIER_DIR)) == 1

    # Verify Hot Tier Stripped
    exported_spans = hot_exporter.export.call_args[0][0]
    exported_span = exported_spans[0]
    assert "gen_ai.content.prompt" not in exported_span.attributes

def test_risky_sampling():
    """Test that RISKY (Blocked) is sampled at 100%."""
    provider, hot_exporter, tiered_processor = setup_telemetry()
    tracer = provider.get_tracer("test")

    with patch("random.random", return_value=0.99):
        with tracer.start_as_current_span("jailbreak_attempt") as span:
            span.set_attribute("guardrail.outcome", "BLOCKED")
            span.set_attribute("gen_ai.content.prompt", "Bad prompt")

    # Verify Cold Tier
    assert len(os.listdir(COLD_TIER_DIR)) == 1

    # Verify Hot Tier Stripped
    exported_spans = hot_exporter.export.call_args[0][0]
    exported_span = exported_spans[0]
    assert "gen_ai.content.prompt" not in exported_span.attributes
    assert "guardrail.outcome" in exported_span.attributes

if __name__ == "__main__":
    try:
        test_read_sampling()
        print("✅ test_read_sampling passed")
        test_write_sampling()
        print("✅ test_write_sampling passed")
        test_risky_sampling()
        print("✅ test_risky_sampling passed")

        # Clean up
        shutil.rmtree(COLD_TIER_DIR)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
