from nemoguardrails.actions import action

@action(name="RetrieveKnowledgeAction")
def retrieve_knowledge_mock(events=None, context=None):
    """
    Mock RetrieveKnowledgeAction to satisfy standard library 'generate_bot_message' flow.
    Returns empty list/None to indicate no knowledge retrieved.
    """
    print("DEBUG: RetrieveKnowledgeAction mock called.")
    return []
