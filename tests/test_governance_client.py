
import pytest
from unittest.mock import MagicMock, patch
from src.governance.client import OPAClient

def test_opa_client_boolean_allow():
    """Test that OPAClient correctly handles boolean True as ALLOW."""
    client = OPAClient()

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        decision = client.evaluate_policy({"action": "execute_trade", "amount": 50000})
        assert decision == "ALLOW"

def test_opa_client_boolean_deny():
    """Test that OPAClient correctly handles boolean False as DENY."""
    client = OPAClient()

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": False}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        decision = client.evaluate_policy({"action": "execute_trade", "amount": 150000})
        assert decision == "DENY"

def test_opa_client_string_manual_review():
    """Test that OPAClient still handles string results."""
    client = OPAClient()

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "MANUAL_REVIEW"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        decision = client.evaluate_policy({"action": "execute_trade", "amount": 999999})
        assert decision == "MANUAL_REVIEW"
