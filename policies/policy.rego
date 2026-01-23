package banking.governance

# --- Aggregation Logic (The Tri-State Protocol) ---

# Final Decision Object
analysis = {"status": "DENY", "reason": reason} {
    reason := deny[msg] # Pick any deny message
} else = {"status": "ALLOW", "reason": "Policy explicitly allowed"} {
    allow
} else = {"status": "UNCERTAIN", "reason": "No matching rule found. System 2 simulation required."} {
    true
}

# --- Base Rules (Sets) ---

default allow = false

# Rule: Allow basic transactions if risk is low
allow {
    input.action == "transfer"
    input.amount < 10000
    input.risk_score < 0.5
}

# Rule: Allow high-value transactions ONLY with 2FA
allow {
    input.action == "transfer"
    input.amount >= 10000
    input.auth_method == "mfa"
}

# Rule: Allow blocking transactions if risk is high (System 2 Logic)
# (Unless overridden by generated causal deny rules)
allow {
    input.action == "block_transaction"
    input.risk_score > 0.9
}

# Rule: Allow execution of trades with moderate risk
allow {
    input.action == "execute_trade"
    input.risk_score < 0.5
}

# Note: 'deny' rules are additive and come from this file OR generated files.
# The 'analysis' rule above aggregates them.
