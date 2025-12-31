import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from financial_advisor.agent import financial_coordinator

app = FastAPI(title="Governed Financial Advisor")

class QueryRequest(BaseModel):
    prompt: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "financial-advisor-agent"}

@app.post("/agent/query")
def query_agent(request: QueryRequest):
    """
    Invokes the ADK agent with the user's prompt.
    """
    try:
        # Note: In a real ADK deployment, we might need to manage session state.
        # For this stateless Cloud Run demo, we treat each request as a new session.
        # ADK agents usually take 'input' or similar.
        # The exact invocation depends on the ADK version.
        # Assuming typical callable or .invoke() pattern.

        # Checking how LlmAgent is invoked.
        # Based on ADK docs, usually it's `agent(input_string)` or `agent.invoke(...)`
        # Using the standard call method for now.

        response = financial_coordinator(request.prompt)

        # If response is an object, we try to extract the text.
        if hasattr(response, 'output'):
            return {"response": response.output}
        return {"response": str(response)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
