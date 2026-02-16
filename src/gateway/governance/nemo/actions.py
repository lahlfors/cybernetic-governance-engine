import logging
from typing import Optional

from nemoguardrails.actions import action
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

logger = logging.getLogger("NeMo.Actions")

# Initialize Presidio Engines globally to avoid re-loading on every request
# This requires 'en_core_web_sm' to be installed.
try:
    # Use small Spacy model as requested
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }

    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    nlp_engine = provider.create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    anonymizer = AnonymizerEngine()
    logger.info("✅ Presidio Analyzer & Anonymizer Initialized (Model: en_core_web_sm).")
except Exception as e:
    logger.error(f"❌ Failed to initialize Presidio: {e}")
    analyzer = None
    anonymizer = None

@action(is_system_action=True)
async def mask_sensitive_data(text: str, source: str = "input") -> str:
    """
    Masks PII in the given text using Presidio.

    Args:
        text: The text to analyze and mask.
        source: 'input' or 'output' (for logging/context).

    Returns:
        The text with PII replaced by placeholders (e.g., <EMAIL_ADDRESS>).
    """
    if not text:
        return text

    if not analyzer or not anonymizer:
        logger.warning("Presidio not initialized. Returning text unmasked.")
        return text

    try:
        # 1. Analyze
        results = analyzer.analyze(
            text=text,
            language='en',
            entities=[
                "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON",
                "CREDIT_CARD", "US_SSN"
            ]
        )

        # 2. Anonymize
        if not results:
            return text

        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=results
        )

        masked_text = anonymized_result.text

        if masked_text != text:
            logger.info(f"🛡️ PII Detected & Masked in {source}: {len(results)} entities found.")
            # logger.debug(f"Original: {text} -> Masked: {masked_text}") # Avoid logging original PII in prod

        return masked_text

    except Exception as e:
        logger.error(f"Error during PII masking: {e}")
        # Fail open (return original) or fail closed (return empty/error)?
        # For PII, fail safe usually implies blocking or redaction, but crashing isn't good.
        # We'll return the original but log heavily, assuming the LLM might catch it or it's a trade-off.
        return text
