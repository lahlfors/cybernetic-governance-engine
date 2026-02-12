
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.gateway.server.main import stream_chat_response, app, mcp
from fastapi.testclient import TestClient

# Mock the Rails instance and its stream_async method
@pytest.fixture
def mock_rails():
    with patch("src.gateway.server.main.get_rails") as mock_get_rails:
        rails_mock = MagicMock()
        mock_get_rails.return_value = rails_mock
        yield rails_mock

@pytest.mark.asyncio
async def test_stream_chat_response_success(mock_rails):
    # Setup mock stream
    async def mock_stream(messages):
        yield "Hello"
        yield " World"

    mock_rails.stream_async.side_effect = mock_stream

    chunks = []
    async for chunk in stream_chat_response("Hi"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello World"
    mock_rails.stream_async.assert_called_once()

@pytest.mark.asyncio
async def test_stream_chat_response_violation(mock_rails):
    # Setup mock stream to raise exception
    async def mock_stream(messages):
        yield "Unsafe"
        raise Exception("Safety Violation")

    mock_rails.stream_async.side_effect = mock_stream

    chunks = []
    async for chunk in stream_chat_response("Bad prompt"):
        chunks.append(chunk)

    response = "".join(chunks)
    assert "Unsafe" in response
    assert "[SYSTEM INTERVENTION]: 🛡️ Blocked: Safety Violation" in response

def test_http_endpoint(mock_rails):
    # Setup mock stream for sync call (TestClient runs app in thread/loop usually, but stream_async needs careful mocking)
    # FastAPIs TestClient uses requests, which is sync. The app uses async generator.
    # We need to ensure the mock works within the loop.

    async def mock_stream(messages):
        yield "HTTP"
        yield " Response"

    mock_rails.stream_async.side_effect = mock_stream

    client = TestClient(app)
    response = client.post("/chat", json={"query": "test"})

    assert response.status_code == 200
    assert response.text == "HTTP Response"

@pytest.mark.asyncio
async def test_mcp_tool(mock_rails):
    # Verify the tool logic directly
    async def mock_stream(messages):
        yield "MCP"
        yield " Tool"

    mock_rails.stream_async.side_effect = mock_stream

    # Access the tool function decorated by fastmcp
    # Use mcp.get_tool() which is async
    tool = await mcp.get_tool("ask_sovereign_advisor")

    # Tool execution
    ctx = MagicMock()
    # FastMCP tools are async
    # The tool yields chunks.

    # We need to simulate how FastMCP calls the tool.
    # The tool defined in main.py is an async generator.

    result_chunks = []
    # tool.fn is the decorated function
    async for chunk in tool.fn("test", ctx):
        result_chunks.append(chunk)

    assert "".join(result_chunks) == "MCP Tool"
