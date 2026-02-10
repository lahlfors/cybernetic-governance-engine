
try:
    from google.adk.models.lite_llm import LiteLlm
    print("LiteLlm imported successfully")
except ImportError as e:
    print(f"ImportError: {e}")
    # try identifying available modules
    import google.adk.models
    print(f"google.adk.models contents: {dir(google.adk.models)}")
