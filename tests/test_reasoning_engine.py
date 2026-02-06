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
from unittest.mock import MagicMock, patch
from src.governed_financial_advisor.reasoning_engine import FinancialAdvisorEngine

@patch("src.governed_financial_advisor.reasoning_engine.create_nemo_manager")
@patch("src.governed_financial_advisor.reasoning_engine.create_graph")
def test_reasoning_engine_initialization(mock_create_graph, mock_create_nemo):
    """
    Test that FinancialAdvisorEngine initializes correctly.
    """
    mock_app = MagicMock()
    mock_create_graph.return_value = mock_app
    mock_create_nemo.return_value = MagicMock()

    engine = FinancialAdvisorEngine(project="test-project", location="us-central1")

    # Assert initial state
    assert engine.project == "test-project"
    assert engine.app is None

    # Call set_up
    engine.set_up()

    assert engine.app == mock_app
    mock_create_graph.assert_called_once()
    mock_create_nemo.assert_called_once()

@patch("src.governed_financial_advisor.reasoning_engine.create_graph")
def test_reasoning_engine_query(mock_create_graph):
    """
    Test that query() method invokes the graph and returns correct format.
    """
    mock_app = MagicMock()
    # Mock return value of app.invoke
    mock_result = {
        "messages": [
            MagicMock(content="First message"),
            MagicMock(content="Final response")
        ],
        "plan": ["step1", "step2"],
        "execution_result": {"status": "success"},
        "evaluation_result": {"safe": True}
    }
    mock_app.invoke.return_value = mock_result
    mock_create_graph.return_value = mock_app

    engine = FinancialAdvisorEngine()
    # Manually inject app since we skip set_up
    engine.app = mock_app

    response = engine.query(prompt="Analyze GOOG")

    assert response["response"] == "Final response"
    assert response["state_snapshot"]["plan"] == ["step1", "step2"]
    mock_app.invoke.assert_called_once()
