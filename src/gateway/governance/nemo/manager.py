"""
Factory for creating NeMo Guardrails manager with vLLM/Llama support.
"""
import logging
import os
from typing import Any, List, Optional, AsyncIterator
import json

import nest_asyncio
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.context import streaming_handler_var
from nemoguardrails.llm.providers import register_llm_provider
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from src.governed_financial_advisor.infrastructure.telemetry.nemo_exporter import NeMoOTelCallback
from src.governed_financial_advisor.infrastructure.config_manager import config_manager
from src.gateway.governance.nemo.vllm_client import VLLMLLM
# Explicitly import actions to ensure they are available for registration
from src.gateway.governance.nemo.actions import (
    check_approval_token,
    check_data_latency,
    check_drawdown_limit,
    check_slippage_risk,
    check_atomic_execution,
    invoke_vllm_fallback,
)

# Configure Logging
if os.getenv("ENABLE_LOGGING", "true").lower() == "true":
    logger = logging.getLogger("NeMoManager")
else:
    logger = logging.getLogger("NeMoManager")
    logger.addHandler(logging.NullHandler())

# --- Monkeypatch NeMo Sensitive Data Detection to use en_core_web_sm ---
try:
    from nemoguardrails.library.sensitive_data_detection import actions as sdd_actions
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    import spacy

    class SafeAnalyzer(AnalyzerEngine):
        def analyze(self, text, **kwargs):
            if text is None:
                return []
            return super().analyze(text=text, **kwargs)

    def _get_analyzer_patch(score_threshold: float = 0.4):
        try:
            import spacy
            if not spacy.util.is_package("en_core_web_lg"):
                 logger.warning("en_core_web_lg not found, PII detection might fail.")
        except:
            pass

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        return SafeAnalyzer(nlp_engine=nlp_engine, default_score_threshold=score_threshold)

    sdd_actions._get_analyzer = _get_analyzer_patch
    logger.info("✅ Monkeypatched NeMo Sensitive Data Detection to use SafeAnalyzer + en_core_web_lg")
except ImportError as e:
    logger.warning(f"⚠️ Could not patch Sensitive Data Detection: {e}")
except Exception as e:
    logger.warning(f"⚠️ Error patching Sensitive Data Detection: {e}")
tracer = trace.get_tracer(__name__)


def create_nemo_manager(config_path: str = "config/rails") -> LLMRails:
    """
    Creates and initializes a NeMo Guardrails manager with vLLM support.
    """
    try:
        nest_asyncio.apply()
    except Exception:
        pass

    # Register our custom provider
    register_llm_provider("vllm_llama", VLLMLLM)
    
    # Resolve config path
    if not os.path.exists(config_path):
        cwd_path = os.path.join(os.getcwd(), config_path)
        if os.path.exists(cwd_path):
            config_path = cwd_path
        else:
            # Look relative to project root if running from elsewhere
            base_dir = os.path.dirname(os.path.abspath(__file__))
            # We are in src/gateway/governance/nemo/, so ../../../../config/rails
            possible_path = os.path.abspath(os.path.join(base_dir, "../../../../config/rails"))
            if os.path.exists(possible_path):
                config_path = possible_path

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"NeMo Guardrails config not found at: {config_path}")

    print(f"DEBUG: Loading NeMo config from {config_path}")
    config = RailsConfig.from_path(config_path)

    # --- Deduplicate Flows (Workaround for double-loading issue) ---
    if hasattr(config, "flows"):
        unique_flows = {}
        original_count = len(config.flows)
        deduped_list = []
        seen_names = set()
        
        for flow in config.flows:
            # Check flow attributes - Colang 2.0 flows should have 'name' or 'id'
            flow_name = getattr(flow, "name", None)
            if not flow_name:
                flow_name = getattr(flow, "id", None)
            
            if not flow_name:
                # Flow might be unnamed or structure is different, keep it to be safe
                deduped_list.append(flow)
                continue
                
            if flow_name in seen_names:
                print(f"WARNING: Removing duplicate flow '{flow_name}' to prevent startup crash.")
                continue
            
            seen_names.add(flow_name)
            deduped_list.append(flow)
            
        config.flows = deduped_list
        print(f"DEBUG: Deduplicated flows from {original_count} to {len(config.flows)}")
    # -------------------------------------------------------------
    
    rails = LLMRails(config)

    # Explicitly register actions
    try:
        rails.register_action(check_approval_token, "check_approval_token")
        rails.register_action(check_data_latency, "check_data_latency")
        rails.register_action(check_drawdown_limit, "check_drawdown_limit")
        rails.register_action(check_slippage_risk, "check_slippage_risk")
        rails.register_action(check_atomic_execution, "check_atomic_execution")
        # Register the new fallback action
        rails.register_action(invoke_vllm_fallback, "invoke_vllm_fallback")
        
        print("DEBUG: Registered invoke_vllm_fallback action")
        logger.info("✅ NeMo actions from module registered successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import NeMo actions: {e}")

    # Register local fallback action (always available) - REMOVED OLD ONE
    # rails.register_action(execute_vllm_fallback, "execute_vllm_fallback")


    return rails

# --- Adapters ---

def load_rails() -> LLMRails:
    """Wrapper to maintain consistency with new design."""
    return create_nemo_manager()

def initialize_rails() -> LLMRails:
    """Wrapper for unified gateway."""
    return create_nemo_manager()

async def validate_with_nemo(user_input: str, rails: LLMRails) -> tuple[bool, str]:
    """
    Validates user input using NeMo Guardrails.
    Returns (is_safe: bool, response: str).
    """
    handler = NeMoOTelCallback()
    token = streaming_handler_var.set(handler)

    with tracer.start_as_current_span("guardrails.validate_input") as span:
        try:
            span.set_attribute("guardrails.framework", "nemo")
            span.set_attribute("guardrails.input_length", len(user_input))

            res = await rails.generate_async(
                messages=[{"role": "user", "content": user_input}],
                streaming_handler=handler
            )

            is_safe = True
            response_content = ""

            if res and isinstance(res, dict) and "content" in res:
                content = res["content"]
                if any(phrase in content for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = content
                else:
                    is_safe = True
                    response_content = content

            elif isinstance(res, str):
                 if any(phrase in res for phrase in ["I cannot answer", "policy", "I am programmed", "I am sorry"]):
                    is_safe = False
                    response_content = res
                 else:
                    is_safe = True
                    response_content = res

            verdict = "APPROVED" if is_safe else "REJECTED"
            span.set_attribute("guardrails.outcome", "ALLOWED" if is_safe else "BLOCKED")
            span.set_attribute("risk.verdict", verdict)
            span.set_attribute("guardrails.intervened", not is_safe)

            return is_safe, response_content

        except Exception as e:
            logger.error(f"NeMo Validation Error: {e}")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            return True, ""
        finally:
            streaming_handler_var.reset(token)
