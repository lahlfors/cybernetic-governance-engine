package financial_policy

import rego.v1

# Default to DENY for safety
default result = "DENY"

# High confidence safe
result = "ALLOW" if {
    input.risk_score < 0.3
    not prohibited_asset
}

# The "Gray Zone" - Triggers System 2 Simulation
result = "UNCERTAIN" if {
    input.risk_score >= 0.3
    input.risk_score < 0.7
    # Ensure it's not strictly prohibited, just risky
    not prohibited_asset
}

# Test Trigger for System 2
result = "UNCERTAIN" if {
    input.action == "test_uncertainty"
}

# Helper to check for hard constraints
prohibited_asset if {
    input.asset_type == "crypto_derivative"
}
