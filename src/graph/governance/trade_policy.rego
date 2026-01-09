package financial.trade

default allow = false

# Simple rule: Allow trades under $100k
allow {
    input.action == "execute_trade"
    input.amount <= 100000
}
