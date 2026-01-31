import logging
from typing import Any

# Import Vertex AI integration
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import MODEL_REASONING, Config
from src.agents.risk_analyst.agent import ProposedUCA
from src.governance.judge import JudgeAgent

logger = logging.getLogger("Governance.Transpiler")

class PolicyTranspiler:
    """
    Automated Rule Derivation (Phase 3).
    Converts Risk Analyst UCAs (with Structured Logic) into:
    1. NeMo-compatible Python Actions (Semantic Control)
    2. Rego Policies (Structural Control)

    Upgrade: Uses LLM for Neuro-Symbolic Translation (ARPaCCino Pattern).
    """

    def __init__(self):
        # Initialize LLM for code generation
        try:
            self.llm = ChatGoogleGenerativeAI(
                model=MODEL_REASONING,
                temperature=0.0,
                google_api_key=Config.GOOGLE_API_KEY
            )
            self.judge = JudgeAgent()
            self.use_llm = True
        except Exception as e:
            logger.warning(f"Could not initialize LLM for Transpiler: {e}. Falling back to templates.")
            self.use_llm = False

    def _generate_with_llm(self, prompt: str) -> str:
        """
        Helper to invoke the LLM for code generation.
        """
        if not self.use_llm:
            return None # Trigger fallback

        try:
            response = self.llm.invoke(prompt)
            content = response.content
            # Strip markdown code blocks if present
            if "```python" in content:
                content = content.split("```python", 1)[1]
            elif "```rego" in content:
                content = content.split("```rego", 1)[1]
            elif "```" in content:
                content = content.split("```", 1)[1]

            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]

            return content.strip()
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return None # Trigger fallback

    def _generate_nemo_template(self, uca: ProposedUCA) -> str:
        """Fallback template for Python generation."""
        logic = uca.constraint_logic

        # 1. Slippage / Volume Check
        if logic.variable == "order_size" or "volume" in logic.threshold:
            threshold_multiplier = logic.threshold.split("*")[0].strip()
            if not threshold_multiplier.replace('.', '', 1).isdigit():
                threshold_multiplier = "0.01" # Fallback

            return f"""
def check_slippage_risk(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard}: Blocks market orders exceeding {threshold_multiplier} of daily volume.
    Condition: {logic.condition}
    '''
    order_type = context.get("order_type", "MARKET")
    order_size = float(context.get("order_size", 0))
    daily_vol = float(context.get("daily_volume", 1000000))

    if order_type == "MARKET" and order_size > (daily_vol * {threshold_multiplier}):
        # UCA Detected: {uca.category}
        return False

    return True
"""

        # 2. Latency Check
        if logic.variable == "latency":
            limit = logic.threshold
            return f"""
def check_data_latency(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard}: Blocks trades if data latency > {limit}ms.
    '''
    # Mock check - in prod read from context['market_data_timestamp']
    current_latency = 50 # Mock
    if current_latency > {limit}:
        return False
    return True
"""

        # 3. Drawdown Check
        if logic.variable == "drawdown":
            limit = logic.threshold
            return f"""
def check_drawdown_limit(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard}: Blocks buy orders if drawdown > {limit}%.
    '''
    current_drawdown = float(context.get("drawdown_pct", 0))
    if current_drawdown > {limit}:
        return False
    return True
"""

        # 4. Atomic Execution Check
        if logic.variable == "time_delta_legs":
            return f"""
def check_atomic_execution(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard}: Ensures multi-leg trades complete atomically.
    '''
    # Simplified mock
    legs_completed = context.get("legs_completed", 0)
    legs_required = context.get("legs_required", 2)
    if legs_completed < legs_required:
        return False # Stopped Too Soon
    return True
"""

        return f"# No template for {uca.description}"

    def _generate_rego_template(self, uca: ProposedUCA) -> str:
        """Fallback template for Rego generation."""
        logic = uca.constraint_logic

        # 1. Slippage / Volume Check
        if logic.variable == "order_size" or "volume" in logic.threshold:
            threshold_multiplier = logic.threshold.split("*")[0].strip()
            if not threshold_multiplier.replace('.', '', 1).isdigit():
                threshold_multiplier = "0.01"

            return f"""
# Enforce: {uca.hazard}
# Condition: {logic.condition}
decision = "DENY" if {{
    input.action == "execute_trade"
    input.order_type == "MARKET"
    # Ensure input.daily_volume is provided or default to a safe value
    daily_vol := object.get(input, "daily_volume", 1000000)
    input.amount > (daily_vol * {threshold_multiplier})
}}
"""

        # 2. Latency Check
        if logic.variable == "latency":
            limit = logic.threshold
            return f"""
# Enforce: {uca.hazard}
# Condition: {logic.condition}
decision = "DENY" if {{
    input.action == "execute_trade"
    latency := object.get(input, "latency_ms", 0)
    latency > {limit}
}}
"""

        # 3. Drawdown Check
        if logic.variable == "drawdown":
            limit = logic.threshold
            return f"""
# Enforce: {uca.hazard}
# Condition: {logic.condition}
decision = "DENY" if {{
    input.action == "execute_trade"
    input.side == "BUY"
    drawdown := object.get(input, "current_drawdown_pct", 0)
    drawdown > {limit}
}}
"""

        # 4. Atomic Execution Check
        if logic.variable == "time_delta_legs":
             return f"""
# Enforce: {uca.hazard}
# Condition: {logic.condition}
decision = "DENY" if {{
    input.action == "execute_multileg_trade"
    completed := object.get(input, "legs_completed", 0)
    required := object.get(input, "legs_required", 2)
    completed < required
}}
"""
        return f"# No Rego template for {uca.description}"

    def generate_nemo_action(self, uca: ProposedUCA) -> str:
        """
        Transpiles a single UCA into a Python function string using LLM or Fallback.
        """
        logger.info(f"Transpiling UCA to Python: {uca.description}")
        logic = uca.constraint_logic

        if self.use_llm:
            prompt = f"""
You are an Expert Python Engineer specializing in NeMo Guardrails.
Task: Write a Python function based on the following Hazard Description.

Hazard: {uca.hazard}
Description: {uca.description}
Constraint Logic:
- Variable: {logic.variable}
- Operator: {logic.operator}
- Threshold: {logic.threshold}
- Condition: {logic.condition}

Requirements:
1. Function name should be descriptive (e.g., check_slippage_risk).
2. Arguments: (context: Dict[str, Any], event: Dict[str, Any]) -> bool.
3. Return False if the hazard is detected (violation), True otherwise.
4. Use `context.get()` with safe defaults.
5. Include docstring.
6. OUTPUT ONLY THE PYTHON CODE. NO MARKDOWN.
"""
            result = self._generate_with_llm(prompt)
            if result:
                return result

        logger.warning("Using Template Fallback for Python Transpilation")
        return self._generate_nemo_template(uca)

    def generate_rego_policy(self, uca: ProposedUCA) -> str:
        """
        Transpiles a single UCA into a Rego rule block using LLM or Fallback.
        Includes a 'Judge Agent' loop to verify the generated code matches the intent.
        """
        logger.info(f"Transpiling UCA to Rego: {uca.description}")
        logic = uca.constraint_logic

        if self.use_llm:
            prompt = f"""
You are an Expert OPA Rego Developer.
Task: Write a Rego deny rule based on the following Hazard Description.

Hazard: {uca.hazard}
Description: {uca.description}
Constraint Logic:
- Variable: {logic.variable}
- Operator: {logic.operator}
- Threshold: {logic.threshold}
- Condition: {logic.condition}

Requirements:
1. Rule should assign `decision = "DENY"` if the violation occurs.
2. Input is accessible via `input`.
3. Use `object.get(input, "key", default)` for safety.
4. Include comments explaining the rule.
5. OUTPUT ONLY THE REGO CODE. NO MARKDOWN.
"""
            result = self._generate_with_llm(prompt)

            # Verify with Judge Agent
            if result:
                is_valid = self.judge.verify(uca.description, result)
                if is_valid:
                    return result
                else:
                    logger.warning(f"Judge Agent rejected generated Rego for {uca.hazard}. Falling back to template.")

        logger.warning("Using Template Fallback for Rego Transpilation")
        return self._generate_rego_template(uca)

    def generate_safety_params(self, ucas: list[ProposedUCA]) -> dict[str, Any]:
        """
        Extracts safety parameters from UCAs for dynamic configuration (Phase 3.5).
        Returns a dictionary suitable for 'safety_params.json'.
        """
        params = {}
        for uca in ucas:
            logic = uca.constraint_logic

            # Extract Drawdown Limit
            if logic.variable == "drawdown":
                try:
                    # Logic threshold might be a string like "4.5" or "0.045"
                    val = float(logic.threshold)
                    # Normalize: if > 1.0, assume percentage (e.g. 4.5 -> 0.045)
                    if val > 1.0:
                        val = val / 100.0
                    params["drawdown_limit"] = val
                except ValueError:
                    logger.warning(f"Could not parse drawdown threshold: {logic.threshold}")

        return params

    def transpile_policy(self, ucas: list[ProposedUCA]) -> tuple[str, str]:
        """
        Generates both Python and Rego policy artifacts.
        Returns: (python_code, rego_code)
        """
        # Python
        py_blocks = [
            "from typing import Dict, Any",
            "",
            "# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER (Neuro-Symbolic)",
            ""
        ]
        for uca in ucas:
            py_blocks.append(self.generate_nemo_action(uca))

        # Rego
        rego_blocks = [
            "package finance.generated",
            "",
            "import rego.v1",
            "",
            "# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER (Neuro-Symbolic)",
            "default decision = \"ALLOW\"",
            ""
        ]
        for uca in ucas:
            rego_blocks.append(self.generate_rego_policy(uca))

        return "\n".join(py_blocks), "\n".join(rego_blocks)

# Global Instance
transpiler = PolicyTranspiler()
