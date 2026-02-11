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
from src.governed_financial_advisor.infrastructure.redis_client import redis_client # Added import

# Adjust path so we can import from src
sys.path.append(".")

from src.gateway.protos import gateway_pb2
from src.gateway.protos import gateway_pb2_grpc
from src.gateway.protos import nemo_pb2
from src.gateway.protos import nemo_pb2_grpc

from src.gateway.core.llm import GatewayClient
from src.gateway.core.policy import OPAClient
from src.gateway.core.tools import execute_trade, TradeOrder
from src.gateway.core.market import market_service
from src.gateway.governance import SymbolicGovernor, GovernanceError

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
        self.llm_client = GatewayClient()
        self.opa_client = OPAClient()

        # Initialize Neuro-Symbolic Governor
        self.symbolic_governor = SymbolicGovernor(
            opa_client=self.opa_client,
            safety_filter=safety_filter,
            consensus_engine=consensus_engine
        )

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
        Executes a tool with strict governance via SymbolicGovernor.
        """
        tool_name = request.tool_name
        logger.info(f"Received Tool Request: {tool_name}")

        try:
            params = json.loads(request.params_json)
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid JSON params: {e}")
            return gateway_pb2.ToolResponse(status="ERROR", error="Invalid JSON")

        # --- NEW SAFETY CONSTRAINT CHECK TOOL (System 3) ---
        if tool_name == "check_safety_constraints":
             # This tool is a 'meta-tool' that runs a dry-run of the governor on a proposed action.
             # params should contain 'target_tool' and 'target_params'
             target_tool = params.get("target_tool", "execute_trade")
             target_params = params.get("target_params", {})

             logger.info(f"🔍 Evaluator verifying proposed action: {target_tool}")

             violations = await self.symbolic_governor.verify(target_tool, target_params)

             if not violations:
                 return gateway_pb2.ToolResponse(status="SUCCESS", output="APPROVED: No violations detected.")
             else:
                 return gateway_pb2.ToolResponse(status="SUCCESS", output=f"REJECTED: {'; '.join(violations)}")

        # --- NEW SAFETY INTERVENTION TOOL (Module 5) ---
        if tool_name == "trigger_safety_intervention":
            reason = params.get("reason", "Unknown Hazard")
            logger.critical(f"🛑 SAFETY INTERVENTION TRIGGERED: {reason}")

            # Set the shared Redis flag
            # In a real K8s setup, all Gateway replicas must see this. Redis provides that.
            redis_client.set("safety_violation", reason)

            return gateway_pb2.ToolResponse(status="SUCCESS", output="INTERVENTION_ACK: System Locked.")

        # 1. Neuro-Symbolic Governance Layer
        # Enforces SR 11-7 (Rules) and ISO 42001 (Policy/Process)
        # We skip read-only/benign tools from heavy governance if needed,
        # but for maximum safety, we could govern everything.
        # Here we maintain the logic of skipping 'check_market_status' and 'verify_content_safety'
        # from OPA/Consensus, as they are low-risk or have their own logic.

        if tool_name not in ["check_market_status", "verify_content_safety"]:
            try:
                await self.symbolic_governor.govern(tool_name, params)
            except GovernanceError as e:
                logger.warning(f"🛡️ Symbolic Governor BLOCKED {tool_name}: {e}")
                return gateway_pb2.ToolResponse(status="BLOCKED", error=str(e))

        # 2. Tool Execution Logic

        if tool_name == "check_market_status":
            symbol = params.get("symbol", "UNKNOWN")
            status = market_service.check_status(symbol)
            return gateway_pb2.ToolResponse(status="SUCCESS", output=status)

        elif tool_name == "get_market_sentiment":
            symbol = params.get("symbol", "UNKNOWN")
            # This is an async method now
            try:
                sentiment = await market_service.get_sentiment(symbol)
                return gateway_pb2.ToolResponse(status="SUCCESS", output=sentiment)
            except Exception as e:
                return gateway_pb2.ToolResponse(status="ERROR", error=str(e))

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
            # Validation (Pydantic)
            try:
                order = TradeOrder(**params)
            except Exception as e:
                return gateway_pb2.ToolResponse(status="ERROR", error=f"Schema Validation Failed: {e}")

            is_dry_run = params.get("dry_run", False)
            if is_dry_run:
                return gateway_pb2.ToolResponse(status="SUCCESS", output="DRY_RUN: APPROVED")

            # State Update (Commit) - only if Governor approved
            # The Governor *verified* the state transition, now we *commit* it.
            amount = params.get("amount", 0)
            safety_filter.update_state(amount)

            # Execute
            try:
                result = await execute_trade(order)
                return gateway_pb2.ToolResponse(status="SUCCESS", output=result)
            except Exception as e:
                logger.error(f"Tool Execution Error: {e}")
                # Rollback state since trade failed
                safety_filter.rollback_state(amount)
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
