
from vertexai.preview import reasoning_engines

class TestEngine:
    def __init__(self):
        pass
    def query(self, prompt: str) -> str:
        return f"Echo: {prompt}"
