
import os
from huggingface_hub import snapshot_download

def download_configs():
    models = [
        "casperhansen/deepseek-r1-distill-llama-8b-awq",
        "meta-llama/Meta-Llama-3.1-8B-Instruct"
    ]
    
    # Files to download (exclude large weights)
    allow_patterns = [
        "*.json",
        "*.py",
        "*.txt",
        "*.model",
        "tokenizer*",
        "config.json",
        "generation_config.json"
    ]
    
    ignore_patterns = [
        "*.safetensors",
        "*.bin",
        "*.pth",
        "*.msgpack",
        "*.h5"
    ]

    token = os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("⚠️ Warning: HUGGING_FACE_HUB_TOKEN not set. Public models might work, but gated ones will fail.")

    for model_id in models:
        print(f"📥 Downloading config for {model_id}...")
        try:
            path = snapshot_download(
                repo_id=model_id,
                allow_patterns=allow_patterns,
                ignore_patterns=ignore_patterns,
                token=token
            )
            print(f"✅ Downloaded {model_id} to {path}")
        except Exception as e:
            print(f"❌ Failed to download {model_id}: {e}")
            # Don't fail the build, just warn? Or fail?
            # Better to fail if it's critical.
            raise e

if __name__ == "__main__":
    download_configs()
