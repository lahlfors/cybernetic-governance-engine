from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Part:
    text: str

@dataclass
class Content:
    parts: List[Part]

@dataclass
class PromptData:
    model: str
    contents: List[Content]
    system_instruction: Optional[Content] = None

@dataclass
class Prompt:
    prompt_data: PromptData
