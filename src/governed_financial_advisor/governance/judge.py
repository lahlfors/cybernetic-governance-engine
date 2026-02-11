import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import Config

logger = logging.getLogger("Governance.Judge")

class JudgeAgent:
    """
    The 'Judge' Agent (Verification Step).
    Back-translates generated Rego policies into Natural Language and compares them
    against the original STAMP Hazard definition to ensure semantic alignment.
    """

    def __init__(self):
        try:
            self.llm = ChatGoogleGenerativeAI(
                model=Config.MODEL_REASONING,
                temperature=0.0,
                google_api_key=Config.GOOGLE_API_KEY
            )
            self.enabled = True
        except Exception as e:
            logger.warning(f"Could not initialize LLM for Judge Agent: {e}. verification will be skipped.")
            self.enabled = False

    def back_translate(self, rego_code: str) -> str:
        """
        Converts Rego code back into a natural language description.
        """
        if not self.enabled:
            return "Verification Skipped (LLM Disabled)"

        prompt = f"""
You are a Governance Auditor.
Task: Translate the following OPA Rego code into a clear, one-sentence Natural Language policy description.
Focus on WHAT is being denied and WHY. Do not use technical jargon like "input.action".

Rego Code:
```rego
{rego_code}
```

Natural Language Translation:
"""
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Back-translation failed: {e}")
            return "Back-translation failed"

    def verify(self, original_hazard_desc: str, rego_code: str) -> bool:
        """
        Verifies if the Rego code accurately reflects the original hazard.
        Returns True if semantically aligned.
        """
        if not self.enabled:
            return True # Fail open if LLM down, or False if strict safety required.

        back_translation = self.back_translate(rego_code)

        prompt = f"""
Role: You are a Logic Verifier.
Task: Compare the ORIGINAL INTENT with the IMPLEMENTED LOGIC (Back-translation).
Determine if they match.

Original Hazard Description:
"{original_hazard_desc}"

Implemented Logic (Derived from Code):
"{back_translation}"

Constraint:
- Return "TRUE" if the implementation strictly enforces the hazard or is a valid subset.
- Return "FALSE" if the implementation misses the key constraint or enforces something completely different.

Reasoning:
"""
        try:
            response = self.llm.invoke(prompt)
            decision = response.content.strip().upper()

            logger.info(f"Judge Verification:\nOriginal: {original_hazard_desc}\nTranslated: {back_translation}\nDecision: {decision}")

            return "TRUE" in decision
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
