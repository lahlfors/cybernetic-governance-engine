
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from deployment.lib.renderer import generate_vllm_manifest
from deployment.lib.config import load_config
from deployment.lib.utils import load_dotenv

def main():
    load_dotenv()
    config = load_config()
    config["project"] = {"id": "laah-cybernetics"}
    
    # Check if we need to load from env for reasoning
    model_reasoning = os.environ.get("MODEL_REASONING")
    if not model_reasoning:
        print("MODEL_REASONING env var not set")
        return

    reasoning_config = config.copy()
    reasoning_config["model"] = {
        "name": model_reasoning,
        "quantization": "awq" if "awq" in model_reasoning.lower() else None,
        "max_model_len": "32768",
        "gpu_memory_utilization": "0.9",
        "enforce_eager": True,
        "enable_prefix_caching": True,
        "served_name": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    }
    
    # Hardcode accelerator for now (gpu)
    accelerator_kind = "gpu"
    
    manifest = generate_vllm_manifest(accelerator_kind, reasoning_config, app_name="vllm-reasoning")
    with open("vllm-reasoning-manual.yaml", "w") as f:
        f.write(manifest)
    print("Manifest written to vllm-reasoning-manual.yaml")

if __name__ == "__main__":
    main()
