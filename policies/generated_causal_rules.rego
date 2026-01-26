package policies.causal_generated

# METADATA
# title: Causal Safety Constraints
# description: Automatically induced from Causal Engine simulations.
# generated_by: scripts/causal_policy_induction.py
# timestamp: 2026-01-26T14:26:22.193745

# Default: Allow unless unsafe
default allow = true

# Constraint: Do not block high-tenure customers due to high churn risk (Insult Effect)
deny[msg] {
    input.action == "block_transaction"
    input.user.tenure_years >= 0.0
    msg := sprintf("CAUSAL SAFETY VIOLATION: Blocking users with tenure >= %.1f years causes unacceptable churn risk.", [0.0])
}
