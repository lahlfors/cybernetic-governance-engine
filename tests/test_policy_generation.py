import pytest
import os

def test_policy_files_exist():
    assert os.path.exists("policies/policy.rego")
    assert os.path.exists("policies/generated_causal_rules.rego")

def test_generated_policy_content():
    with open("policies/generated_causal_rules.rego", "r") as f:
        content = f.read()

    assert "package banking.governance" in content
    assert "deny {" in content
    assert "input.action == \"block_transaction\"" in content
    assert "input.tenure_years >=" in content

    # Check if a numeric threshold was found and written
    import re
    match = re.search(r"input\.tenure_years >= (\d+\.?\d*)", content)
    assert match, "Could not find tenure threshold in generated policy"
    threshold = float(match.group(1))
    print(f"Found generated threshold: {threshold}")
    assert threshold >= 0.0

if __name__ == "__main__":
    pass
