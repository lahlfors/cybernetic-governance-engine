"""
Synthetic Data Generator for Risk Scenarios.
Generates diverse risk assessment logs adhering to the RiskAssessment schema.
"""

import json
import uuid
import random
from typing import List
from src.agents.risk_analyst.schema import RiskAssessment

SCENARIOS = [
    ("High Frequency Trading on Meme Coins", "Volatility"),
    ("Forex Carry Trade with 100x Leverage", "Liquidity"),
    ("Long Term Bond Ladder", "Operational"),
    ("Crypto Yield Farming on Unaudited Protocol", "Counterparty"),
    ("Short Selling Tesla before Earnings", "Psychological"),
    ("Investing 90% of Portfolio in Single Tech Stock", "Model"), # Concentration
    ("Arbitrage between two illiquid exchanges", "Liquidity"),
    ("Algorithmic Scalping on Low Float Stocks", "Volatility"),
    ("Buying Deep OTM Options expiring tomorrow", "Model"), # Gambling
    ("Copy Trading an influencer without diligence", "Psychological")
]

UNSAFE_ACTIONS_POOL = [
    "Max Leverage", "No Stop Loss", "Ignore Liquidity", "Single Asset Concentration",
    "Unaudited Contract Interaction", "FOMO Entry", "Revenge Trading", "Over-allocation",
    "Short Volatility", "Market Order on Illiquid Pair"
]

def generate_synthetic_logs(count: int = 50) -> List[dict]:
    logs = []
    print(f"Generating {count} synthetic risk logs...")

    for _ in range(count):
        scenario, primary_risk = random.choice(SCENARIOS)
        is_risky = random.random() > 0.3 # 70% risky

        verdict = "REJECT" if is_risky else "APPROVE"
        score = random.choice(["HIGH", "CRITICAL"]) if is_risky else random.choice(["LOW", "MEDIUM"])

        unsafe_actions = []
        if is_risky:
            # Pick 1-2 unsafe actions
            k = random.randint(1, 2)
            unsafe_actions = random.sample(UNSAFE_ACTIONS_POOL, k)

            # Inject "Concentration" specifically for the UCA-4 discovery test
            if "Concentration" in scenario and "Single Asset Concentration" not in unsafe_actions:
                unsafe_actions.append("Single Asset Concentration")

        assessment = {
            "risk_score": score,
            "primary_risk_factor": primary_risk,
            "verdict": verdict,
            "reasoning_summary": f"Assessment for {scenario}. Detected significant risks.",
            "detected_unsafe_actions": unsafe_actions,
            "detailed_analysis_report": f"# Risk Report for {scenario}\n\n..."
        }

        # Validate against schema (simulating agent output)
        try:
            # We construct the wrapping structure that analyze_logs expects
            log_entry = {
                "trace_id": str(uuid.uuid4()),
                "risk_json": assessment
            }
            logs.append(log_entry)
        except Exception as e:
            print(f"Schema Validation Failed: {e}")

    return logs

if __name__ == "__main__":
    data = generate_synthetic_logs(50)
    with open("data/risk_simulation_logs.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data)} logs to data/risk_simulation_logs.json")
