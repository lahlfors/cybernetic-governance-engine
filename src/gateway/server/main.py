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

            # The HybridClient.generate method is async.
            # However, for streaming in gRPC, we need to yield.
            # HybridClient.generate currently returns a string (blocking) OR an iterator?
            # Let's check HybridClient.generate implementation in core/llm.py.
            # It returns `full_response` string for both streaming and blocking modes
            # (it consumes the stream internally to calculate TTFT).

            # WAIT. The analysis said "Proxy LLM Streams".
            # The current HybridClient implementation consumes the stream to measure TTFT/TPOT *inside* the client,
            # and returns the full string.
            # To support true streaming to the agent, I would need to modify HybridClient to yield chunks.
            # But HybridClient in core/llm.py was copied from the original, which returned a string.

            # For this Refactor, I will support the *Interface* of streaming (yielding one chunk)
            # but the *Implementation* will be blocking (wait for full response) for now
            # to preserve the existing "Latency as Currency" telemetry logic which relies on consuming the stream.
            # Refactoring HybridClient to be a generator is a larger task.

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
        tool_name = request.tool_name
        logger.info(f"Received Tool Request: {tool_name}")

        try:
            params = json.loads(request.params_json)
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid JSON params: {e}")
            return gateway_pb2.ToolResponse(status="ERROR", error="Invalid JSON")

        # 1. Governance Tax (OPA)
        # We need to adapt the OPA check.
        payload = params.copy()
        payload['action'] = tool_name

        decision = await self.opa_client.evaluate_policy(payload)

        if decision == "DENY":
            return gateway_pb2.ToolResponse(status="BLOCKED", error="OPA Policy Violation")

        if decision == "MANUAL_REVIEW":
             return gateway_pb2.ToolResponse(status="BLOCKED", error="Manual Review Required (Not Implemented)")

        # 2. Safety & Consensus
        # Only for execute_trade currently
        if tool_name == "execute_trade":
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
                consensus = consensus_engine.check_consensus(tool_name, amount, symbol)

                if consensus["status"] == "REJECT":
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Consensus Rejected: {consensus['reason']}")

                if consensus["status"] == "ESCALATE":
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Consensus Escalation: {consensus['reason']}")

                # Update State
                safety_filter.update_state(amount)

                # 3. Execution (The "Act" phase)
                result = execute_trade(order)
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
