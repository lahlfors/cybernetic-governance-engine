package system.authz
import rego.v1

# Deny access by default
default allow = false

# Allow access if the token provided matches the injected secret
allow if {
    input.identity == data.auth_token
}
