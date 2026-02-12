import argparse
import sys
import uvicorn
import logging
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastmcp import FastMCP, Context
import nest_asyncio

# Apply nest_asyncio to allow nested event loops if needed (e.g. for FastMCP/NeMo interaction)
nest_asyncio.apply()

# --- Import Guardrails Manager ---
try:
    from src.governed_financial_advisor.utils.nemo_manager import initialize_rails
except ImportError as e:
    # Fail fast if core dependencies are missing
    sys.stderr.write(f"CRITICAL: Could not import 'initialize_rails': {e}\nCheck path.\n")
    sys.exit(1)

# ==========================================
# 1. Core Logic (Shared by MCP & HTTP)
# ==========================================
_rails_instance = None

def get_rails():
    global _rails_instance
    if _rails_instance is None:
        _rails_instance = initialize_rails()
    return _rails_instance

async def stream_chat_response(query: str):
    """
    Generator that streams the guardrailed response.
    Used by both the MCP Tool and the HTTP Endpoint.
    """
    rails = get_rails()
    messages = [{"role": "user", "content": query}]

    try:
        # Optimistic Streaming
        stream = rails.stream_async(messages=messages)
        async for chunk in stream:
            yield chunk

    except Exception as e:
        # The "Kill Switch" - stops stream on safety violation
        yield f"\n\n[SYSTEM INTERVENTION]: 🛡️ Blocked: {str(e)}"

# ==========================================
# 2. MCP Server Definition (Agent Interface)
# ==========================================
mcp = FastMCP("SovereignGateway")

@mcp.tool(name="ask_sovereign_advisor")
async def ask_sovereign_advisor(query: str, ctx: Context) -> str:
    """
    Queries the Sovereign Financial Advisor via the Secure Gateway.
    Response is streamed and monitored by NeMo Guardrails.
    """
    ctx.info(f"MCP Query: {query}")
    full_response = ""

    async for chunk in stream_chat_response(query):
        yield chunk
        full_response += chunk

    # FastMCP tools can yield partial results but should not return a value if they are generators.
    # The 'full_response' is not needed to be returned here for streaming tools.

# ==========================================
# 3. HTTP Server Definition (Service Interface)
# ==========================================
# This replaces the old gRPC service with a standard REST API
app = FastAPI(title="Sovereign Gateway")

class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Standard HTTP endpoint for microservices/frontends.
    Returns a StreamingResponse (Server-Sent Events style).
    """
    return StreamingResponse(
        stream_chat_response(request.query),
        media_type="text/plain"
    )

# ==========================================
# 4. Unified Entry Point
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign Gateway Entry Point")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Run mode: 'stdio' for Agents (Claude), 'http' for Services (REST API)."
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP mode")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for HTTP mode")

    args = parser.parse_args()

    if args.mode == "stdio":
        # --- MCP Mode (Agent) ---
        # Used by Claude Desktop. Logs must go to stderr.
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        mcp.run()

    elif args.mode == "http":
        # --- HTTP Mode (Service) ---
        # Replaces gRPC. Used by internal apps.
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Starting HTTP Gateway on {args.host}:{args.port}")

        # We can mount MCP over SSE if we want, but keeping them separate is cleaner.
        # uvicorn runs the FastAPI app defined above.
        uvicorn.run(app, host=args.host, port=args.port)
