from dataclasses import dataclass


@dataclass
class Part:
    text: str

@dataclass
class Content:
    parts: list[Part]

@dataclass
class PromptData:
    model: str
    contents: list[Content]
    system_instruction: Content | None = None

@dataclass
class Prompt:
    prompt_data: PromptData
