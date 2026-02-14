
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Import the GatewayClient to test header injection
from src.gateway.core.llm import GatewayClient
from src.governed_financial_advisor.utils.telemetry import genai_span, record_completion

class TestHybridTelemetry(unittest.TestCase):
    def setUp(self):
        # Setup Tracing
        self.provider = TracerProvider()
        self.exporter = MagicMock()
        self.processor = SimpleSpanProcessor(self.exporter)
        self.provider.add_span_processor(self.processor)

        # Patch get_tracer to use our provider
        self.patcher_tracer = patch("src.governed_financial_advisor.utils.telemetry.get_tracer")
        self.mock_get_tracer = self.patcher_tracer.start()
        self.mock_get_tracer.return_value = self.provider.get_tracer("test")

        # Ensure trace.get_current_span works by setting global provider (if allowed)
        try:
            trace.set_tracer_provider(self.provider)
        except Exception:
            pass # Provider might already be set

    def tearDown(self):
        self.patcher_tracer.stop()

    def test_payload_capture_restored(self):
        """Verify that genai_span DOES capture prompt content (for LangSmith)."""
        prompt = "Explain quantum computing"
        completion = "It is complex."

        with genai_span("test_span", prompt=prompt, model="gpt-4-turbo") as span:
            record_completion(span, completion)

        # Force export
        self.processor.force_flush()

        # Inspect exported span
        spans = self.exporter.export.call_args[0][0]
        self.assertEqual(len(spans), 1)
        span = spans[0]

        # Assertions
        attributes = span.attributes
        self.assertEqual(attributes.get("gen_ai.content.prompt"), prompt, "Prompt should be captured")
        self.assertEqual(attributes.get("gen_ai.content.completion"), completion, "Completion should be captured")

    @patch("src.gateway.core.llm.AsyncOpenAI")
    def test_header_injection(self, mock_openai_cls):
        """Verify that X-Trace-Id header is injected into LLM requests."""
        # Use asyncio.run for async test method
        async def run_test():
            # Mock Client
            mock_client = AsyncMock()
            mock_openai_cls.return_value = mock_client

            # Mock Response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Test Response"
            mock_client.chat.completions.create.return_value = mock_response

            client = GatewayClient()

            # Run Generate inside a span context
            tracer = self.provider.get_tracer("test")
            with tracer.start_as_current_span("root_span") as root_span:
                # We need to manually set the span in context because start_as_current_span
                # sets it in the ContextVars, which should propagate to the async call.
                await client.generate("Hello", mode="chat")

                # Verify Trace ID Injection
                # Extract call args
                call_kwargs = mock_client.chat.completions.create.call_args.kwargs
                extra_headers = call_kwargs.get("extra_headers", {})

                trace_id_hex = format(root_span.get_span_context().trace_id, "032x")
                self.assertEqual(extra_headers.get("X-Trace-Id"), trace_id_hex)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
