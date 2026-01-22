package banking.governance

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
allow {
    input.action == "block_transaction"
    input.risk_score > 0.9
}

# Rule: Allow execution of trades with moderate risk (example from previous code)
allow {
    input.action == "execute_trade"
    input.risk_score < 0.5
}
