package financial.trade

# Default deny all trades
default allow = false

# Allow trades under $100,000
allow {
    input.action == "execute_trade"
    input.amount <= 100000
}

# Require manual review for trades between $100k and $500k
manual_review {
    input.action == "execute_trade"
    input.amount > 100000
    input.amount <= 500000
}

# Deny trades over $500k outright
deny {
    input.action == "execute_trade"
    input.amount > 500000
}
