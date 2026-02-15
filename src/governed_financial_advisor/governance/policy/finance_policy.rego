package finance

import rego.v1

# Default output: Deny
default allow = "DENY"

# Rule: Allow Market Analysis (Safe Read-Only)
allow = "ALLOW" if {
    input.action == "market_analysis"
}

# --- Basic Access Control (RBAC) ---
# Ensure only valid roles are even considered.
allowed_roles := {"junior", "senior"}

# Rule: Deny if role is unknown (Implicitly handled by default, but explicit for clarity)
allow = "DENY" if {
    input.action != "market_analysis"
    not input.trader_role in allowed_roles
}

# --- Risk Limits ---

# Rule: JUNIOR ALLOW
# Junior bankers can trade up to $5,000 without review.
allow = "ALLOW" if {
    input.trader_role == "junior"
    input.amount <= 5000
    input.currency != "BTC"
}

# Rule: SENIOR ALLOW
# Senior bankers can trade up to $500,000 without review.
allow = "ALLOW" if {
    input.trader_role == "senior"
    input.amount <= 500000
    input.currency != "BTC"
}

# Rule: JUNIOR MANUAL REVIEW
# Junior bankers trigger review between $5,001 and $10,000.
allow = "MANUAL_REVIEW" if {
    input.trader_role == "junior"
    input.amount > 5000
    input.amount <= 10000
    input.currency != "BTC"
}

# Rule: SENIOR MANUAL REVIEW
# Senior bankers trigger review between $500,001 and $1,000,000.
allow = "MANUAL_REVIEW" if {
    input.trader_role == "senior"
    input.amount > 500000
    input.amount <= 1000000
    input.currency != "BTC"
}

# --- Risk Profile Rules (Semantic Mapping) ---
# Task C: Map "Aggressive" to Allowed (Growth strategy)
allow = "ALLOW" if {
    input.risk_profile == "Aggressive"
}

allow = "ALLOW" if {
    input.risk_profile == "Moderate"
}

allow = "ALLOW" if {
    input.risk_profile == "Conservative"
}

allow = "DENY" if {
    input.risk_profile == "Speculative"
    not input.trader_role == "senior"
}
