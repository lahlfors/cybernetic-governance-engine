"""
Data Analysis Script for Green Agent Evolution.
This script demonstrates how to parse structured Risk Analyst logs to seed STPA rules.
"""

import json
import uuid
import collections
from typing import List, Dict

def analyze_logs(logs: List[Dict]):
    print(f"--- Analyzing {len(logs)} Risk Logs ---")

    # 1. Filter for Rejections
    rejections = [l for l in logs if l["risk_json"]["verdict"] == "REJECT"]
    print(f"Found {len(rejections)} rejections.")

    # 2. Extract Unsafe Actions
    all_unsafe_actions = []
    for r in rejections:
        actions = r["risk_json"].get("detected_unsafe_actions", [])
        all_unsafe_actions.extend(actions)

    # 3. Cluster/Count
    counter = collections.Counter(all_unsafe_actions)
    print("\n--- Identified Unsafe Action Clusters (Frequency) ---")
    for action, count in counter.most_common():
        print(f"- {action}: {count}")

    # 4. Suggest Rules
    print("\n--- Suggested STPA Rules ---")
    if counter["Max Leverage"] > 0 or counter["Unlimited Risk"] > 0:
        print("[SUGGESTION] Formalize Rule: UCA-UNBOUNDED-RISK")
        print("  Trigger: 'Leverage > 10x' OR 'Short Volatility'")

    if counter["Market Order on Illiquid Asset"] > 0:
        print("[SUGGESTION] Formalize Rule: UCA-LIQUIDITY-SHOCK")
        print("  Trigger: 'Order Size > 1% ADV'")

    if counter["Single Asset Concentration"] > 0:
        print("[SUGGESTION] Formalize Rule: UCA-CONCENTRATION")
        print("  Trigger: 'Portfolio Weight > 20%' OR 'Single Asset'")

if __name__ == "__main__":
    # Load from file if available, else use mock
    try:
        with open("data/risk_simulation_logs.json", "r") as f:
            logs = json.load(f)
        analyze_logs(logs)
    except FileNotFoundError:
        print("No log file found, running mock data...")
        # ... (mock data code from before) ...
