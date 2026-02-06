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
from src.gateway.protos import nemo_pb2
from src.gateway.protos import nemo_pb2_grpc

from src.gateway.core.llm import HybridClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service

from src.governed_financial_advisor.governance.consensus import consensus_engine
from src.governed_financial_advisor.governance.safety import safety_filter

logger = logging.getLogger("Gateway.Server")

# Configure JSON Logging
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

        # Connect to NeMo gRPC
        nemo_url = os.getenv("NEMO_URL", "nemo-service:8000")
        # Ensure we strip http:// if present for gRPC
        if nemo_url.startswith("http://"):
            nemo_url = nemo_url.replace("http://", "")

        logger.info(f"Connecting to NeMo Guardrails at {nemo_url}...")
        self.nemo_channel = grpc.aio.insecure_channel(nemo_url)
        self.nemo_stub = nemo_pb2_grpc.NeMoGuardrailsStub(self.nemo_channel)

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
        tool_name = request.tool_name
        logger.info(f"Received Tool Request: {tool_name}")

        try:
            params = json.loads(request.params_json)
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid JSON params: {e}")
            return gateway_pb2.ToolResponse(status="ERROR", error="Invalid JSON")

        # 1. Governance Tax (OPA) - REST
        if tool_name not in ["check_market_status", "verify_content_safety"]:
            payload = params.copy()
            payload['action'] = tool_name

            decision = await self.opa_client.evaluate_policy(payload)

            if decision == "DENY":
                return gateway_pb2.ToolResponse(status="BLOCKED", error="OPA Policy Violation")
            if decision == "MANUAL_REVIEW":
                 return gateway_pb2.ToolResponse(status="BLOCKED", error="Manual Review Required")

        # 2. Safety & Consensus

        if tool_name == "check_market_status":
            symbol = params.get("symbol", "UNKNOWN")
            status = market_service.check_status(symbol)
            return gateway_pb2.ToolResponse(status="SUCCESS", output=status)

        # --- SEMANTIC SAFETY TOOL (NeMo gRPC) ---
        elif tool_name == "verify_content_safety":
            text = params.get("text", "")
            try:
                nemo_req = nemo_pb2.VerifyRequest(input=text)
                nemo_resp = await self.nemo_stub.Verify(nemo_req)

                if nemo_resp.status == "SUCCESS":
                    return gateway_pb2.ToolResponse(status="SUCCESS", output="SAFE")
                else:
                    return gateway_pb2.ToolResponse(status="BLOCKED", error=f"NeMo Blocked: {nemo_resp.response}")
            except grpc.RpcError as e:
                logger.error(f"NeMo gRPC Failed: {e}")
                # Fail Closed
                return gateway_pb2.ToolResponse(status="BLOCKED", error="Safety Service Unavailable")

        elif tool_name == "execute_trade":
            try:
                try:
                    order = TradeOrder(**params)
                except Exception as e:
                    return gateway_pb2.ToolResponse(status="ERROR", error=f"Schema Validation Failed: {e}")

                cbf_result = safety_filter.verify_action(tool_name, params)
                if cbf_result.startswith("UNSAFE"):
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Safety Filter: {cbf_result}")

                amount = params.get("amount", 0)
                symbol = params.get("symbol", "UNKNOWN")
                consensus = await consensus_engine.check_consensus(tool_name, amount, symbol)

                if consensus["status"] == "REJECT":
                     return gateway_pb2.ToolResponse(status="BLOCKED", error=f"Consensus Rejected: {consensus['reason']}")

                is_dry_run = params.get("dry_run", False)
                if is_dry_run:
                    return gateway_pb2.ToolResponse(status="SUCCESS", output="DRY_RUN: APPROVED")

                safety_filter.update_state(amount)
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

    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"🚀 Gateway Server (gRPC) starting on port {port}...")

    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())
