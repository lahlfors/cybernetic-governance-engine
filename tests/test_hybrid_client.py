import pytest
import respx
from httpx import Response
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from src.infrastructure.llm_client import HybridClient

# Mock data
VLLM_URL = "http://vllm-mock:8000/v1"

# To mock a streaming response with httpx/respx, we provide an iterator of bytes.
# Format: data: {json}\n\n
STREAM_CHUNK_1 = b'data: {"choices": [{"delta": {"content": "Fast "}, "index": 0}]}\n\n'
STREAM_CHUNK_2 = b'data: {"choices": [{"delta": {"content": "path "}, "index": 0}]}\n\n'
STREAM_CHUNK_3 = b'data: {"choices": [{"delta": {"content": "result"}, "index": 0}]}\n\n'
STREAM_DONE = b'data: [DONE]\n\n'

@pytest.fixture
def hybrid_client():
    # Patch genai.Client to prevent any auth attempts during test setup
    with patch("src.infrastructure.llm_client.genai.Client") as mock_genai_cls:
        client = HybridClient(
            vllm_base_url=VLLM_URL,
            # Use a large threshold for success tests
            fallback_threshold_ms=5000.0,
            vertex_project="test-project"
        )
        # Mock the vertex client structure for fallback tests
        mock_instance = mock_genai_cls.return_value
        # Ensure aio.models.generate_content is an async mock
        mock_instance.aio.models.generate_content = AsyncMock()
        mock_instance.aio.models.generate_content.return_value.text = "Vertex fallback result"

        # Inject the mock instance into the client
        client._vertex_client = mock_instance

        yield client

# Helper for async iteration
async def async_chunks(chunks):
    for chunk in chunks:
        yield chunk

@pytest.mark.asyncio
async def test_fast_path_success(hybrid_client):
    """Test that valid, fast vLLM streaming response is returned."""
    with respx.mock(base_url=VLLM_URL, assert_all_called=False) as respx_mock:

        async def stream_response(request):
            return Response(
                200,
                content=async_chunks([STREAM_CHUNK_1, STREAM_CHUNK_2, STREAM_CHUNK_3, STREAM_DONE]),
                headers={"Content-Type": "text/event-stream"}
            )

        respx_mock.post("/chat/completions").mock(side_effect=stream_response)

        result = await hybrid_client.generate("Hello")
        assert result == "Fast path result"
        assert respx_mock.calls.call_count >= 1

@pytest.mark.asyncio
async def test_fast_path_error_triggers_fallback(hybrid_client):
    """Test that vLLM 500 error triggers fallback."""
    with respx.mock(base_url=VLLM_URL, assert_all_called=False) as respx_mock:
        # Mock vLLM failure
        respx_mock.post("/chat/completions").mock(
            return_value=Response(500)
        )

        result = await hybrid_client.generate("Hello")

        assert result == "Vertex fallback result"
        # Verify vLLM was called
        assert respx_mock.calls.call_count >= 1

@pytest.mark.asyncio
async def test_fast_path_latency_triggers_fallback(hybrid_client):
    """Test that vLLM TTFT timeout triggers fallback."""
    # Set a short threshold for this test
    hybrid_client.fallback_threshold_ms = 100.0

    with respx.mock(base_url=VLLM_URL, assert_all_called=False) as respx_mock:
        # Mock vLLM slow stream start
        async def slow_stream_response(request):
            # Sleep 300ms before yielding first byte
            await asyncio.sleep(0.3)
            return Response(
                200,
                content=async_chunks([STREAM_CHUNK_1, STREAM_DONE]),
                headers={"Content-Type": "text/event-stream"}
            )

        respx_mock.post("/chat/completions").mock(side_effect=slow_stream_response)

        result = await hybrid_client.generate("Hello")

        assert result == "Vertex fallback result"
