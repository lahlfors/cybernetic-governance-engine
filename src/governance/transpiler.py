import logging
from typing import List, Dict, Any, Tuple
from src.governance.stpa import UCA

logger = logging.getLogger("Governance.Transpiler")

class PolicyTranspiler:
    """
    Automated Rule Derivation (Phase 3).
    Converts Risk Analyst UCAs (with Structured Logic) into:
    1. NeMo-compatible Python Actions (Semantic Control)
    2. Rego Policies (Structural Control)
    """

    def generate_nemo_action(self, uca: UCA) -> str:
        """
        Transpiles a single UCA into a Python function string using the `logic`.
        """
        logger.info(f"Transpiling UCA to Python: {uca.description}")
        logic = uca.logic

        if not logic:
            return f"# No logic definition found for UCA: {uca.description}"

        # 1. Slippage / Volume Check
        if logic.variable == "order_size" or "volume" in logic.threshold:
            threshold_multiplier = logic.threshold.split("*")[0].strip() # Extract '0.01' from '0.01 * daily_volume'
            if not threshold_multiplier.replace('.', '', 1).isdigit():
                threshold_multiplier = "0.01" # Fallback

            return f"""
def check_slippage_risk(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard.value}: Blocks market orders exceeding {threshold_multiplier} of daily volume.
    Condition: {logic.condition}
    '''
    order_type = context.get("order_type", "MARKET")
    order_size = float(context.get("order_size", 0))
    daily_vol = float(context.get("daily_volume", 1000000))

    if order_type == "MARKET" and order_size > (daily_vol * {threshold_multiplier}):
        # UCA Detected: {uca.type.value}
        return False

    return True
"""

        # 2. Latency Check
        if logic.variable == "latency":
            limit = logic.threshold
            return f"""
def check_data_latency(context: Dict[str, Any] = {{}}, event: Dict[str, Any] = {{}}) -> bool:
    '''
    Enforces {uca.hazard.value}: Blocks trades if data latency > {limit}ms.
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
    Enforces {uca.hazard.value}: Blocks buy orders if drawdown > {limit}%.
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
    Enforces {uca.hazard.value}: Ensures multi-leg trades complete atomically.
    '''
    # Simplified mock
    legs_completed = context.get("legs_completed", 0)
    legs_required = context.get("legs_required", 2)
    if legs_completed < legs_required:
        return False # Stopped Too Soon
    return True
"""

        # Fallback
        return f"# No template found for UCA: {uca.description}"

    def generate_rego_policy(self, uca: UCA) -> str:
        """
        Transpiles a single UCA into a Rego rule block.
        """
        logger.info(f"Transpiling UCA to Rego: {uca.description}")
        logic = uca.logic

        if not logic:
            return f"# No logic definition for UCA: {uca.description}"

        # Generic Allow Rule Structure
        # allow { not deny }
        # deny { ... condition ... }

        # 1. Slippage / Volume Check
        if logic.variable == "order_size" or "volume" in logic.threshold:
            threshold_multiplier = logic.threshold.split("*")[0].strip()
            if not threshold_multiplier.replace('.', '', 1).isdigit():
                threshold_multiplier = "0.01"

            return f"""
# Enforce: {uca.hazard.value}
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
# Enforce: {uca.hazard.value}
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
# Enforce: {uca.hazard.value}
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
# Enforce: {uca.hazard.value}
# Condition: {logic.condition}
decision = "DENY" if {{
    input.action == "execute_multileg_trade"
    completed := object.get(input, "legs_completed", 0)
    required := object.get(input, "legs_required", 2)
    completed < required
}}
"""
        return f"# No Rego template for UCA: {uca.description}"

    def generate_safety_params(self, ucas: List[UCA]) -> Dict[str, Any]:
        """
        Extracts safety parameters from UCAs for dynamic configuration (Phase 3.5).
        Returns a dictionary suitable for 'safety_params.json'.
        """
        params = {}
        for uca in ucas:
            logic = uca.logic
            if not logic:
                continue

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

    def transpile_policy(self, ucas: List[UCA]) -> Tuple[str, str]:
        """
        Generates both Python and Rego policy artifacts.
        Returns: (python_code, rego_code)
        """
        # Python
        py_blocks = [
            "from typing import Dict, Any",
            "",
            "# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER",
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
            "# AUTOMATICALLY GENERATED BY GOVERNANCE TRANSPILER",
            "default decision = \"ALLOW\"",
            ""
        ]
        for uca in ucas:
            rego_blocks.append(self.generate_rego_policy(uca))

        return "\n".join(py_blocks), "\n".join(rego_blocks)

# Global Instance
transpiler = PolicyTranspiler()
