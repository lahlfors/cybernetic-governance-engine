package banking.governance

default allow = false

# Rule: Allow basic transactions if risk is low AND not denied
allow {
    input.action == "transfer"
    input.amount < 10000
    input.risk_score < 0.5
    not deny
}

# Rule: Allow high-value transactions ONLY with 2FA AND not denied
allow {
    input.action == "transfer"
    input.amount >= 10000
    input.auth_method == "mfa"
    not deny
}

# Rule: Allow blocking transactions if risk is high (System 2 Logic) AND not denied
# This is where the Causal Induction rules (in generated_causal_rules.rego) will intervene.
allow {
    input.action == "block_transaction"
    input.risk_score > 0.9
    not deny
}

# Rule: Allow execution of trades with moderate risk AND not denied
allow {
    input.action == "execute_trade"
    input.risk_score < 0.5
    not deny
}
