import asyncio
import json
import logging
import os
import sys
import time
from concurrent import futures

import grpc
from opentelemetry import trace
from pythonjsonlogger import jsonlogger

# Adjust path so we can import from src
sys.path.append(".")

from src.gateway.protos import gateway_pb2
from src.gateway.protos import gateway_pb2_grpc
from src.gateway.core.llm import HybridClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service

# Import Governance Logic (Assuming these remain as shared libraries for now)
# In a true microservice split, these would be moved to gateway/core completely.
from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter

logger = logging.getLogger("Gateway.Server")

# Configure JSON Logging for Cloud Run (Stackdriver)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(timestamp)s %(severity)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[logHandler])

tracer = trace.get_tracer("gateway.server")

class GatewayService(gateway_pb2_grpc.GatewayServicer):
    def __init__(self):
        logger.info("Initializing Gateway Service Components...")
        self.llm_client = HybridClient()
        self.opa_client = OPAClient()
        logger.info("Gateway Service Ready.")

    async def Chat(self, request, context):
        """
        Bi-directional streaming LLM Proxy.
        """
        logger.info(f"Received Chat Request: Model={request.model}")

        # Convert repeated Message field to list of dicts
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Prepare kwargs for HybridClient
        kwargs = {}
        if request.temperature:
            kwargs['temperature'] = request.temperature
        if request.guided_json:
            try:
                kwargs['guided_json'] = json.loads(request.guided_json)
            except:
                pass
        if request.guided_regex:
            kwargs['guided_regex'] = request.guided_regex
        if request.guided_choice:
            try:
                kwargs['guided_choice'] = json.loads(request.guided_choice)
            except:
                pass

        try:
            # We treat 'Chat' as streaming unless mode is verifier
            mode = request.mode if request.mode else "chat"

            # Extract arguments
            prompt_text = messages[-1]['content']
            system_instruction = request.system_instruction

            full_response = await self.llm_client.generate(
                prompt=prompt_text,
                system_instruction=system_instruction,
                mode=mode,
                **kwargs
            )

            # Yield the full response as one chunk (or split it if we wanted to fake it)
            yield gateway_pb2.ChatResponse(content=full_response, is_final=True)

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return

    async def ExecuteTool(self, request, context):
        """
        Executes a tool with strict governance.
        """
        start_time = time.time()
        tool_name = request.tool_name
        logger.info(f"Received Tool Request: {tool_name}")

        try:
            params = json.loads(request.params_json)
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid JSON params: {e}")
            return gateway_pb2.ToolResponse(status="ERROR", error="Invalid JSON")

        # 1. Governance Tax (OPA)
        # Calculate current latency (simulating "Latency as Currency")
        # In a real distributed trace, we would extract this from context.
        # Here we approximate it as time since request received.
        current_latency_ms = (time.time() - start_time) * 1000

        payload = params.copy()
        payload['action'] = tool_name

        # Pass latency to OPA check for Bankruptcy Protocol
        decision = await self.opa_client.evaluate_policy(payload, current_latency_ms=current_latency_ms)

            if decision == "DENY":
                return gateway_pb2.ToolResponse(status="BLOCKED", error="OPA Policy Violation")

            if decision == "MANUAL_REVIEW":
                 # Production readiness: Log alert instead of just error string
                 logger.critical(f"MANUAL REVIEW REQUIRED for {tool_name} | Params: {params}")
                 return gateway_pb2.ToolResponse(status="BLOCKED", error="Manual Review Triggered - Admin Notified.")

        # 2. Safety & Consensus

        # --- MARKET CHECK TOOL ---
        if tool_name == "check_market_status":
            symbol = params.get("symbol", "UNKNOWN")
            status = market_service.check_status(symbol)
            return gateway_pb2.ToolResponse(status="SUCCESS", output=status)

        # --- SEMANTIC SAFETY TOOL (NeMo Proxy) ---
        elif tool_name == "verify_content_safety":
            text = params.get("text", "")
            # In a real deployment, this calls the NeMo Guardrails Service (Layer 0)
            # or uses a local Guardrails instance.
            # For now, we implement a basic robust check to replace the mock.
            if "jailbreak" in text.lower() or "ignore previous" in text.lower():
                 return gateway_pb2.ToolResponse(status="BLOCKED", error="Semantic Safety Violation (Jailbreak Pattern)")
            return gateway_pb2.ToolResponse(status="SUCCESS", output="SAFE")

        # --- TRADE EXECUTION TOOL ---
        elif tool_name == "execute_trade":
            try:
                # Validate Schema first
                try:
                    order = TradeOrder(**params)
                except Exception as e:
                    return gateway_pb2.ToolResponse(status="ERROR", error=f"Schema Validation Failed: {e}")

                # CBF Check
                cbf_result = safety_filter.verify_action(tool_name, params)
                if cbf_result.startswith("UNSAFE"):
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Safety Filter: {cbf_result}")

                # Consensus Check
                amount = params.get("amount", 0)
                symbol = params.get("symbol", "UNKNOWN")
                # Await the async consensus check
                consensus = await consensus_engine.check_consensus(tool_name, amount, symbol)

                if consensus["status"] == "REJECT":
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Consensus Rejected: {consensus['reason']}")

                if consensus["status"] == "ESCALATE":
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Consensus Escalation: {consensus['reason']}")

                # DRY RUN CHECK (Moved here to cover Safety/Consensus too)
                is_dry_run = params.get("dry_run", False)
                if is_dry_run:
                    logger.info(f"DRY RUN (System 3 Check): {tool_name} APPROVED by all gates.")
                    return gateway_pb2.ToolResponse(status="SUCCESS", output="DRY_RUN: APPROVED by OPA, Safety, and Consensus.")

                # Update State
                safety_filter.update_state(amount)

                # 3. Execution (The "Act" phase)
                result = await execute_trade(order)
                return gateway_pb2.ToolResponse(status="SUCCESS", output=result)

            except Exception as e:
                logger.error(f"Tool Execution Error: {e}")
                return gateway_pb2.ToolResponse(status="ERROR", error=str(e))

        else:
            return gateway_pb2.ToolResponse(status="ERROR", error=f"Unknown tool: {tool_name}")

async def serve():
    port = os.getenv("PORT", "50051")
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    gateway_pb2_grpc.add_GatewayServicer_to_server(GatewayService(), server)

    # Cloud Run expects us to listen on $PORT
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"🚀 Gateway Server starting on port {port}...")

    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())
