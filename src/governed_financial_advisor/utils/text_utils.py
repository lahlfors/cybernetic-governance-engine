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
    
    # Handle unclosed <think> tags (e.g. if generation stopped mid-stream)
    # This will remove everything after <think> if the closing tag is missing.
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    
    # Also handle standalone </think> if the opening tag was missed or split
    cleaned = re.sub(r'.*?</think>', '', cleaned, flags=re.DOTALL)
    
    return cleaned.strip()
