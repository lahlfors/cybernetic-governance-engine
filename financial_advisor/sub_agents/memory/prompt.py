from financial_advisor.prompt_utils import Prompt, PromptData, Content, Part

# Design Pattern: Vertex AI Prompt Class
# https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/prompt-classes

MEMORY_MANAGER_PROMPT = Prompt(
    prompt_data=PromptData(
        model="gemini-2.5-pro",
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
You are the Memory Manager for a Cybernetic Financial Advisor.

Your Goal:
Maintain a high-quality, concise, and privacy-preserving record of the user's financial context, risk tolerance, and investment constraints.

Instructions:
1.  **Ingest** raw interaction logs provided by the main advisor agent.
2.  **Synthesize** this information into a structured User Profile.
3.  **Retrieve** relevant context when asked by the main agent.
4.  **Resolve Conflicts:** If new information contradicts old information, prioritize the NEW information but note the change.

Constraints:
- Do NOT hallucinate user preferences.
- If data is contradictory, note the contradiction.
- Discard ephemeral "chit-chat". Only store actionable financial context.
"""
                    )
                ]
            )
        ],
        system_instruction=Content(
            parts=[Part(text="You are a strict JSON-compliant memory governance system.")]
        ),
    )
)

def get_memory_instruction() -> str:
    """
    Extracts the compiled instruction string from the Vertex Prompt object
    for compatibility with ADK LlmAgent.
    """
    # In a full Vertex Agent Engine integration, we would create/update the prompt resource here.
    # For ADK local usage, we return the text.
    return MEMORY_MANAGER_PROMPT.prompt_data.contents[0].parts[0].text
