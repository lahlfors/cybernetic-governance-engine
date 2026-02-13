
import requests
import json
import time

# Use local port 8001
URL = "http://localhost:8003/v1/chat/completions"

def debug_deepseek():
    print(f"🔍 Debugging DeepSeek-R1 on {URL}...")
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Get the current stock price for a ticker",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "The stock ticker symbol, e.g. AAPL"},
                    },
                    "required": ["ticker"]
                }
            }
        }
    ]
    
    payload = {
        "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. You have access to tools. You MUST use the `get_stock_price` tool to answer the question."},
            {"role": "user", "content": "What is the price of NVDA right now?"}
        ],
        "tools": tools,
        "tool_choice": "required",
        "temperature": 0.0,
        "max_tokens": 2048
    }
    
    try:
        response = requests.post(URL, json=payload, timeout=120)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Inspect structure
            choices = data.get("choices", [])
            if not choices:
                print("No choices returned!")
                return
                
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls")
            
            print(f"\n📝 Raw Content:\n{content}")
            if tool_calls:
                print(f"\n🛠️ Tool Calls:\n{json.dumps(tool_calls, indent=2)}")
            else:
                print("\n⚠️ No Tool Calls found in response message.")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_deepseek()
