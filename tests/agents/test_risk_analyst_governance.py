
import sys
import unittest
from unittest.mock import MagicMock, patch

# 1. Mock dependencies

# Mock pydantic
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def model_json_schema(cls):
        return {"type": "object", "title": cls.__name__}

    @classmethod
    def model_validate_json(cls, json_str):
        import json
        data = json.loads(json_str)
        return cls(**data)

    def model_dump(self):
        return self.__dict__

def MockField(*args, **kwargs):
    return None

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MockField
sys.modules["pydantic"] = mock_pydantic

# Mock yaml
sys.modules["yaml"] = MagicMock()

# Mock httpx
sys.modules["httpx"] = MagicMock()

# Mock google
mock_google = MagicMock()
mock_adk = MagicMock()
mock_agent = MagicMock()
mock_adk.Agent = mock_agent

# Mock tools
mock_tools = MagicMock()
mock_transfer = MagicMock()
mock_transfer.__name__ = "transfer_to_agent"
mock_tools.transfer_to_agent = mock_transfer

mock_google.adk = mock_adk
mock_adk.tools = mock_tools

sys.modules["google"] = mock_google
sys.modules["google.adk"] = mock_adk
sys.modules["google.adk.tools"] = mock_tools
sys.modules["google.adk.agents"] = MagicMock()

# Mock config
mock_settings = MagicMock()
mock_settings.MODEL_REASONING = "gemini-2.5-pro"
sys.modules["config"] = MagicMock()
sys.modules["config.settings"] = mock_settings

# Mock src.governance.policy_loader
mock_policy_loader = MagicMock()
sys.modules["src.governance"] = MagicMock()
sys.modules["src.governance.policy_loader"] = mock_policy_loader
mock_policy_loader.PolicyLoader.return_value.format_as_prompt_context.return_value = "Hazard List..."

# Mock src.utils.prompt_utils
sys.modules["src.utils"] = MagicMock()
sys.modules["src.utils.prompt_utils"] = MagicMock()

# Mock src.agents.financial_advisor
sys.modules["src.agents.financial_advisor"] = MagicMock()
sys.modules["src.agents.financial_advisor.agent"] = MagicMock()

# Now import
from src.agents.risk_analyst.agent import perform_governed_risk_assessment, create_risk_analyst_agent, RiskAssessment
from src.infrastructure.governance_client import GovernanceClient

class TestRiskAnalystGovernance(unittest.TestCase):

    def setUp(self):
        pass

    @patch("src.agents.risk_analyst.agent.GovernanceClient")
    def test_perform_governed_risk_assessment(self, MockGovernanceClient):
        """Test that the tool correctly invokes GovernanceClient.generate_structured_sync."""

        mock_client_instance = MockGovernanceClient.return_value

        expected_assessment = RiskAssessment(
            risk_level="Low",
            identified_ucas=[],
            analysis_text="Safe."
        )

        # Mock the synchronous method
        mock_client_instance.generate_structured_sync.return_value = expected_assessment

        context = "Analyze this trade."
        result = perform_governed_risk_assessment(context)

        MockGovernanceClient.assert_called_once()
        mock_client_instance.generate_structured_sync.assert_called_once_with(
            prompt=context,
            schema=RiskAssessment
        )

        self.assertEqual(result, expected_assessment.model_dump())

    def test_create_risk_analyst_agent_registers_tool(self):
        """Test that the factory registers the governance tool."""

        agent = create_risk_analyst_agent()

        self.assertTrue(mock_adk.Agent.called)

        call_args = mock_adk.Agent.call_args
        kwargs = call_args.kwargs

        tools = kwargs.get("tools", [])
        tool_names = [t.__name__ for t in tools]

        self.assertIn("perform_governed_risk_assessment", tool_names)
        self.assertIn("transfer_to_agent", tool_names)

        instruction = kwargs.get("instruction", "")
        self.assertIn("perform_governed_risk_assessment", instruction)

if __name__ == "__main__":
    unittest.main()
