"""
Simple Agent implementation to replace google.adk dependency.
Uses litellm for vLLM/Llama compatibility.
"""
import logging
import json
from typing import Any, Callable, List, Optional
from dataclasses import dataclass

from src.governed_financial_advisor.infrastructure.config_manager import config_manager

logger = logging.getLogger("SimpleAgent")

@dataclass
class FunctionTool:
    fn: Callable
    name: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        if not self.name:
            self.name = self.fn.__name__
        if not self.description:
            self.description = self.fn.__doc__ or "No description provided."

    def to_openai_tool(self):
        """Converts to OpenAI tool format."""
        # Simple schema extraction - for now we assume string query/input
        # In a real scenario, we'd inspect signature or Pydantic model
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query or input text."},
                        # Support for transfer_to_agent args
                        "agent_name": {"type": "string", "description": "Target agent name"}
                    },
                    # We don't enforce required params strictly here for simplicity
                    # "required": ["query"]
                }
            }
        }

def transfer_to_agent(agent_name: str):
    """Transfers control to another agent."""
    return f"TRANSFER_TO: {agent_name}"

class Agent:
    def __init__(
        self,
        model: str,
        name: str,
        instruction: str,
        tools: Optional[List[FunctionTool]] = None,
        output_key: str = "output",
        **kwargs
    ):
        self.model = model
        self.name = name
        self.instruction = instruction
        self.tools = tools or []
        self.output_key = output_key
        self.extra_config = kwargs
        
        # Determine API Base
        from config.settings import Config
        self.api_base = config_manager.get("GATEWAY_API_BASE", Config.GATEWAY_API_BASE)
        self.api_key = config_manager.get("VLLM_API_KEY", "EMPTY")

    def chat(self, user_message: str, history: List[dict] = None) -> str:
        """Synchronous chat."""
        # Use litellm
        import litellm
        
        messages = [{"role": "system", "content": self.instruction}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Prepare tools
        openai_tools = [t.to_openai_tool() for t in self.tools] if self.tools else None
        
        # Litellm call
        model_id = self.model
        if not model_id.startswith("openai/"):
            model_id = f"openai/{model_id}"

        print(f"DEBUG: Agent {self.name} calling {model_id} on {self.api_base}")

        response = litellm.completion(
            model=model_id,
            api_base=self.api_base,
            api_key=self.api_key,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto" if openai_tools else None
        )
        
        msg = response.choices[0].message
        
        # Handle Tool Calls
        if msg.tool_calls:
            # We only support 1 turn of tool execution for simplicity in this replacement
            tool_call = msg.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            tool = next((t for t in self.tools if t.name == function_name), None)
            if tool:
                logger.info(f"Generated Tool Call: {function_name}({arguments})")
                # Execute tool
                # Assuming simple args mapping
                result = tool.fn(**arguments)
                
                # Append tool result
                messages.append(msg)
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id, 
                    "content": str(result)
                })
                
                # Second call to get final answer
                response2 = litellm.completion(
                    model=model_id,
                    api_base=self.api_base,
                    api_key=self.api_key,
                    messages=messages
                )
                return response2.choices[0].message.content
            else:
                return f"Error: Tool {function_name} not found."

        return msg.content

