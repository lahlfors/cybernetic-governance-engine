import random
import json
import time
from locust import HttpUser, task, between, events

# --- 1. Custom Metrics Hooks ---
# We use this to track "business logic" errors (e.g., Guardrail blocks)
# distinct from server crashes (HTTP 500).
REQUEST_TYPE = "Agent_Workflow"

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--agent-endpoint", type=str, env_var="AGENT_ENDPOINT", default="/agent/query", help="The endpoint to hit")

# --- 2. Data Generators ---
TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "JPM", "V", "NVDA", "BRK.B"]
RISK_LEVELS = ["low", "moderate", "high", "speculative"]
TIME_HORIZONS = ["short_term", "medium_term", "long_term"]

class FinancialAdvisorUser(HttpUser):
    # Agents are slow. Users won't hammer the enter key.
    # Wait 5-15 seconds between completion and next request.
    wait_time = between(5, 15)

    @task
    def execute_advisory_workflow(self):
        # Generate random inputs to defeat caching
        ticker = random.choice(TICKERS)
        risk = random.choice(RISK_LEVELS)
        horizon = random.choice(TIME_HORIZONS)

        # Note: The prompt structure here should match what the actual agent expects
        prompt = f"Analyze {ticker} for a {risk} risk portfolio with a {horizon} horizon. Research the stock, create a trading plan, and execute it."

        payload = {
            "prompt": prompt,
            "user_id": f"load_test_user_{random.randint(1, 1000)}",
            "thread_id": f"thread_{random.randint(1, 10000)}"
        }

        # We define a custom name so all random tickers group under one entry in the UI
        request_name = "POST /agent/query"

        # Use the configured endpoint or default
        endpoint = self.environment.parsed_options.agent_endpoint if self.environment.parsed_options else "/agent/query"

        with self.client.post(
            endpoint,
            json=payload,
            name=request_name,
            catch_response=True,
            timeout=120 # Important: LLM agents can take 30s-60s to finish a full chain
        ) as response:

            # --- 3. Validation Logic ---
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Check 1: Did the Guardrail block it?
                    # Depending on API contract, blocked might be a 200 with specific content
                    # or the 'response' field contains the block message.
                    # In server.py: return {"response": msg}

                    resp_text = data.get("response", "")

                    if "cannot answer" in resp_text or "policy" in resp_text.lower():
                        # This counts as a business logic "block" but technically a successful request handling
                        # We might want to track this as a specific event type if possible,
                        # or just consider it success for load testing purposes (system didn't crash).
                        # For now, let's just log it if we were tracking 'compliance rate'.
                        # response.failure(f"Guardrail Blocked: {resp_text}")
                        response.success()
                        return

                    # Check 2: Did the plan actually execute?
                    # Since the response is just text, we might look for success indicators
                    # or if the user wanted structured output we'd check that.
                    # For a generic load test, 200 OK + valid JSON is usually success.
                    response.success()

                except json.JSONDecodeError:
                    response.failure("Response was not valid JSON")

            elif response.status_code == 504:
                response.failure("Gateway Timeout - Agent took too long")

            else:
                response.failure(f"HTTP Error: {response.status_code}")

    # Optional: Health check task to ensure basic connectivity isn't the bottleneck
    @task(weight=1)
    def health_check(self):
        self.client.get("/health", name="Health Check")
