"""
Data Analysis Script for Green Agent Evolution.
This script demonstrates how to parse structured Risk Analyst logs to seed STPA rules.
"""

import json
import uuid
import collections
from typing import List, Dict

# Mock Data: Simulating what the Risk Analyst would output after our prompt change
MOCK_LOGS = [
    {
        "trace_id": str(uuid.uuid4()),
        "risk_json": {
            "risk_score": "HIGH",
            "primary_risk_factor": "Volatility",
            "verdict": "REJECT",
            "reasoning_summary": "Strategy uses 50x leverage on a highly volatile asset class during earnings week.",
            "detected_unsafe_actions": ["Max Leverage", "Earnings Play"]
        }
    },
    {
        "trace_id": str(uuid.uuid4()),
        "risk_json": {
            "risk_score": "CRITICAL",
            "primary_risk_factor": "Liquidity",
            "verdict": "REJECT",
            "reasoning_summary": "Attempting to sell 10% of daily volume in a single market order.",
            "detected_unsafe_actions": ["Market Order on Illiquid Asset", "Volume Spike"]
        }
    },
    {
        "trace_id": str(uuid.uuid4()),
        "risk_json": {
            "risk_score": "LOW",
            "primary_risk_factor": "None",
            "verdict": "APPROVE",
            "reasoning_summary": "Standard DCA strategy into SPY.",
            "detected_unsafe_actions": []
        }
    },
     {
        "trace_id": str(uuid.uuid4()),
        "risk_json": {
            "risk_score": "HIGH",
            "primary_risk_factor": "Volatility",
            "verdict": "REJECT",
            "reasoning_summary": "Shorting VIX implies unlimited risk if volatility spikes.",
            "detected_unsafe_actions": ["Unlimited Risk", "Short Volatility"]
        }
    }
]

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

if __name__ == "__main__":
    analyze_logs(MOCK_LOGS)
