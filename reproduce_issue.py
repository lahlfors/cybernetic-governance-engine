
def check_heuristics(message):
    message = message.lower()
    planner_keywords = ["strategy", "plan", "trade", "buy", "sell", "execution", "risk", "evaluate"]
    data_keywords = ["analyze", "price", "stock", "ticker", "market"]
    
    if any(t in message for t in planner_keywords):
        return "execution_analyst (Planner)"
    elif any(t in message for t in data_keywords):
        return "data_analyst"
    return "FINISH"

test_messages = [
    "Please explain this to me",
    "I want to validatethe result",
    "What is the risk?",
    "Do you have a plan?",
    "Hello there",
    "analyzing data",
]

print(f"{'Message':<30} | {'Route':<25}")
print("-" * 60)
for msg in test_messages:
    route = check_heuristics(msg)
    print(f"{msg:<30} | {route:<25}")
