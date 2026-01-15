from src.governance.transpiler import transpiler
from src.agents.risk_analyst.agent import ProposedUCA, ConstraintLogic

uca = ProposedUCA(
    description="Do not trade when latency is high",
    hazard="Stale Data Execution",
    category="Latency",
    constraint_logic=ConstraintLogic(
        variable="latency",
        operator=">",
        threshold="100",
        condition="latency > 100ms"
    ),
    why="Prevents executing on old prices"
)

py_code, rego_code = transpiler.transpile_policy([uca])

print("--- PYTHON ---")
print(py_code)
print("\n--- REGO ---")
print(rego_code)
