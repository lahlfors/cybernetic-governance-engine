
import unittest
from unittest.mock import MagicMock, patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from src.governed_financial_advisor.utils.telemetry import genai_span, record_completion

class TestLightweightTelemetry(unittest.TestCase):
    def setUp(self):
        # Setup Tracing with Mock Exporter
        self.provider = TracerProvider()
        self.exporter = MagicMock()
        self.processor = SimpleSpanProcessor(self.exporter)
        self.provider.add_span_processor(self.processor)

        # Patch get_tracer to use our provider
        self.patcher = patch("src.governed_financial_advisor.utils.telemetry.get_tracer")
        self.mock_get_tracer = self.patcher.start()
        self.mock_get_tracer.return_value = self.provider.get_tracer("test")

    def tearDown(self):
        self.patcher.stop()

    def test_genai_span_is_lightweight(self):
        """Verify that genai_span does NOT capture heavy prompt content."""
        heavy_prompt = "A" * 10000
        heavy_completion = "B" * 5000

        with genai_span("test_span", prompt=heavy_prompt, model="gpt-4-turbo") as span:
            record_completion(span, heavy_completion)

        # Force export
        self.processor.force_flush()

        # Inspect exported span
        spans = self.exporter.export.call_args[0][0]
        self.assertEqual(len(spans), 1)
        span = spans[0]

        # Assertions
        attributes = span.attributes

        # Should NOT contain the content
        self.assertNotIn("gen_ai.content.prompt", attributes, "Heavy prompt should not be in attributes")
        self.assertNotIn("gen_ai.content.completion", attributes, "Heavy completion should not be in attributes")

        # SHOULD contain metadata
        self.assertEqual(attributes["gen_ai.request.model"], "gpt-4-turbo")
        self.assertEqual(attributes["gen_ai.content.prompt_length"], 10000)
        self.assertEqual(attributes["gen_ai.content.completion_length"], 5000)

if __name__ == "__main__":
    unittest.main()
