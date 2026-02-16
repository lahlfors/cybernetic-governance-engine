import re

def strip_thinking_tags(text: str) -> str:
    """
    Removes <think>...</think> blocks from the text.
    Handles multiline content and ensures whitespace is trimmed.
    """
    if not text:
        return ""
    # Remove <think>...</think> (non-greedy)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned.strip()
