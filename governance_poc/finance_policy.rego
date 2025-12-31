package finance

# Default decision is to BLOCK
default allow = false

# Rule 1: Allow if amount is safe and currency is valid
allow if {
    # Condition: Amount must be less than or equal to 1,000,000
    input.amount <= 1000000

    # Condition: Currency must NOT be BTC
    input.currency != "BTC"
}
