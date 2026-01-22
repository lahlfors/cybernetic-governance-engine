package finance

import data.finance.decision

import rego.v1

# Default output: Deny

# --- Basic Access Control (RBAC) ---
# Ensure only valid roles are even considered.
allowed_roles := {"junior", "senior"}

# Entrypoint for WASM compilation
# Returns true if the decision is ALLOW
allow := decision == "ALLOW"

# Rule: Deny if role is unknown (Implicitly handled by default, but explicit for clarity)
# --- Risk Limits ---
# Rule: JUNIOR ALLOW
# Junior bankers can trade up to $5,000 without review.
# Rule: SENIOR ALLOW
# Senior bankers can trade up to $500,000 without review.
# Rule: JUNIOR MANUAL REVIEW
# Junior bankers trigger review between $5,001 and $10,000.
# Rule: SENIOR MANUAL REVIEW
# Senior bankers trigger review between $500,001 and $1,000,000.
