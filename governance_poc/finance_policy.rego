package finance

import rego.v1

# Default output: Deny
default decision = "DENY"

# Rule: JUNIOR ALLOW
# Junior bankers can trade up to $5,000 without review.
decision = "ALLOW" if {
    input.trader_role == "junior"
    input.amount <= 5000
    input.currency != "BTC"
}

# Rule: SENIOR ALLOW
# Senior bankers can trade up to $500,000 without review.
decision = "ALLOW" if {
    input.trader_role == "senior"
    input.amount <= 500000
    input.currency != "BTC"
}

# Rule: JUNIOR MANUAL REVIEW
# Junior bankers trigger review between $5,001 and $10,000.
decision = "MANUAL_REVIEW" if {
    input.trader_role == "junior"
    input.amount > 5000
    input.amount <= 10000
    input.currency != "BTC"
}

# Rule: SENIOR MANUAL REVIEW
# Senior bankers trigger review between $500,001 and $1,000,000.
decision = "MANUAL_REVIEW" if {
    input.trader_role == "senior"
    input.amount > 500000
    input.amount <= 1000000
    input.currency != "BTC"
}
