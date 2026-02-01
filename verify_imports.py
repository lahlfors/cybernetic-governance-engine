import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

print("Checking imports...")

try:
    print("- Importing graph...")
    from src.governed_financial_advisor.graph.graph import create_graph
    print("  ✅ Graph imported.")
except Exception as e:
    print(f"  ❌ Graph import failed: {e}")
    sys.exit(1)

try:
    print("- Importing supervisor node...")
    from src.governed_financial_advisor.graph.nodes.supervisor_node import supervisor_node
    print("  ✅ Supervisor node imported.")
except Exception as e:
    print(f"  ❌ Supervisor node import failed: {e}")
    sys.exit(1)

try:
    print("- Importing transpiler...")
    from src.governed_financial_advisor.governance.transpiler import transpiler
    print("  ✅ Transpiler imported.")
except Exception as e:
    print(f"  ❌ Transpiler import failed: {e}")
    sys.exit(1)

try:
    print("- Importing financial coordinator...")
    from src.governed_financial_advisor.agents.financial_advisor.agent import financial_coordinator
    print("  ✅ Financial Coordinator imported.")
except Exception as e:
    print(f"  ❌ Financial Coordinator import failed: {e}")
    sys.exit(1)

print("\nAll critical checks passed.")
