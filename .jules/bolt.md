## 2026-02-01 - Gateway Chat History Overhead
**Learning:** The Gateway Service was iterating over the entire chat history (O(N)) to extract just the last message for the prompt, causing unnecessary CPU overhead on large contexts.
**Action:** Use direct indexing `request.messages[-1]` instead of list comprehension when only the last item is needed.
