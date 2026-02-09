# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch

from src.gateway.core.mcp_client import MCPClientWrapper
from src.gateway.core.tools import perform_market_search

@pytest.mark.asyncio
async def test_mcp_client_connection():
    """
    Verifies that MCPClientWrapper initializes correctly in 'stdio' mode.
    """
    config = {
        "mode": "stdio",
        "command": "echo",
        "args": ["hello"],
        "env": {}
    }

    with patch("src.gateway.core.mcp_client.stdio_client") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)

        with patch("src.gateway.core.mcp_client.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session
            mock_session.__aenter__.return_value = mock_session

            client = MCPClientWrapper(config)
            async with client.connect() as session:
                assert session is mock_session
                mock_session.initialize.assert_awaited_once()

@pytest.mark.asyncio
async def test_perform_market_search_tool():
    """
    Verifies the Gateway tool correctly calls the MCP client.
    """
    tool_name = "TIME_SERIES_DAILY"
    args = {"symbol": "IBM"}
    expected_result = "Mock Data for IBM"

    with patch("src.gateway.core.tools.mcp_client_wrapper") as mock_wrapper:

        mock_session = AsyncMock()
        mock_wrapper.connect.return_value.__aenter__.return_value = mock_session

        # FIX: The tool AWAITS call_tool, so the mock return value must be awaitable (or the mock itself must be an AsyncMock)
        # AsyncMock returns an awaitable by default when called.
        # But if we set return_value to a string, it returns a string, which is not awaitable.
        # We need `mock_wrapper.call_tool` to be an AsyncMock that resolves to `expected_result`.

        # Since `mock_wrapper` is a MagicMock (by default from patch), its attributes are MagicMocks.
        # We explicitly set `call_tool` to an AsyncMock.
        mock_wrapper.call_tool = AsyncMock(return_value=expected_result)

        result = await perform_market_search(tool_name, args)

        assert result == expected_result
        mock_wrapper.call_tool.assert_awaited_with(tool_name, args)
