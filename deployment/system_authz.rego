package system.authz

# Deny access by default
default allow := false

# Allow access if the token provided matches the injected secret
allow if {
    input.identity == data.auth_token
}
