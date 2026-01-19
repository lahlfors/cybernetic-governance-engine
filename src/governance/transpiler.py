import logging
from typing import List, Dict, Any, Tuple
from src.agents.risk_analyst.agent import ProposedUCA

logger = logging.getLogger("Governance.Transpiler")

class PolicyTranspiler:
    """
    Automated Rule Derivation (Phase 3).
    Converts Risk Analyst UCAs (with Structured Logic) into:
    1. NeMo-compatible Python Actions (Semantic Control)
    2. Rego Policies (Structural Control)
    """

    def generate_nemo_action(self, uca: ProposedUCA) -> str:
        """
        Transpiles a single UCA into a Python function string using the `constraint_logic`.
        """
        logger.info(f"Transpiling UCA to Python: {uca.description}")
        logic = uca.constraint_logic

        # 1. Slippage / Volume Check
        if logic.variable == "order_size" or "volume" in logic.threshold:
            threshold_multiplier = logic.threshold.split("*")[0].strip() # Extract '0.01' from '0.01 * daily_volume'
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

        # Fallback
        return f"# No template found for UCA: {uca.description}"

    def generate_rego_policy(self, uca: ProposedUCA) -> str:
        """
        Transpiles a single UCA into a Rego rule block.
        """
        logger.info(f"Transpiling UCA to Rego: {uca.description}")
        logic = uca.constraint_logic

        # Generic Allow Rule Structure
        # allow { not deny }
        # deny { ... condition ... }

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
        return f"# No Rego template for UCA: {uca.description}"

    def transpile_policy(self, ucas: List[ProposedUCA]) -> Tuple[str, str]:
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

        # Extract and write Constants first (Dynamic Parameters)
        for uca in ucas:
            logic = uca.constraint_logic
            if logic.variable == "drawdown":
                try:
                    limit_val = float(logic.threshold)
                    py_blocks.append(f"DRAWDOWN_LIMIT = {limit_val}")
                except ValueError:
                    py_blocks.append(f"DRAWDOWN_LIMIT = 4.5 # Fallback from {logic.threshold}")

        py_blocks.append("") # Spacing

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
