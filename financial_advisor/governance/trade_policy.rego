package financial.trade
default allow = false

# Allow logic for tools
allow if {
    input.action == "execute_trade"
    input.amount <= 10000
}
