# src/sandbox/main.py
import io
from contextlib import redirect_stderr, redirect_stdout

import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class CodeExecutionRequest(BaseModel):
    code: str

@app.post("/execute")
async def execute_code(request: CodeExecutionRequest):
    """
    Executes arbitrary Python code in this container.
    WARNING: This is a sandbox. Ensure network policies block sensitive egress.
    """
    # 1. Prepare the Execution Environment
    # We pre-import pandas/yfinance so the agent can use them immediately.
    exec_globals = {
        "pd": pd,
        "yf": yf,
        "print": print
    }

    # 2. Capture Output
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # 3. Execute
            exec(request.code, exec_globals)

        return {
            "status": "success",
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
