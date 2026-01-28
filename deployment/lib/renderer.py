
from pathlib import Path

def generate_vllm_manifest(accelerator, config):
    """Generates the vLLM deployment YAML based on the accelerator and custom args."""
    # Assuming the template is strict relative to the deployment root, but here we are in lib.
    # deployment/lib/renderer.py -> deployment/k8s/vllm-deployment.yaml.tpl
    
    # Use configuration to find template path or default
    # For now assume root relative
    tpl_path = Path("deployment/k8s/vllm-deployment.yaml.tpl")
    if not tpl_path.exists():
        print(f"❌ Template not found: {tpl_path}")
        return None

    with open(tpl_path) as f:
        content = f.read()

    vllm_conf = config.get("vllm", {})
    cluster_acc = config.get("cluster", {}).get("accelerator", {})
    
    # Get image names from config or defaults
    image_tpu = vllm_conf.get("image_tpu", "vllm/vllm-tpu:latest")
    image_gpu = vllm_conf.get("image_gpu", "vllm/vllm-openai:latest")

    if accelerator == "tpu":
        print("ℹ️ Generating TPU-specific vLLM manifest...")
        image_name = image_tpu
        resource_limits = '              google.com/tpu: "8"'
        resource_requests = '              google.com/tpu: "8"'
        env_vars = '            - name: VLLM_TARGET_DEVICE\n              value: "tpu"'
        # TP=8, no quantization, no spec dec
        vllm_args = """            - "--tensor-parallel-size"
            - "8" """
    else:
        # GPU Logic
        # Check accelerator type from config if needed, or rely on passed 'accelerator' arg from k8s.py
        # But we need specifics like 'a100' vs 't4'.
        acc_type_full = cluster_acc.get("type", "nvidia-tesla-t4")
        
        print(f"ℹ️ Generating GPU vLLM manifest (Type: {acc_type_full})...")
        image_name = image_gpu
        resource_limits = '              nvidia.com/gpu: "1"'
        resource_requests = '              nvidia.com/gpu: "1"'
        
        model_conf = config.get("model", {})
        model_name = model_conf.get("name", "meta-llama/Meta-Llama-3.1-8B-Instruct")
        quantization = model_conf.get("quantization")

        # Base settings
        vllm_args_list = [
            '            - "--model"',
            f'            - "{model_name}"',
            '            - "--served-model-name"',
            f'            - "{model_name}"'
        ]
        
        if quantization:
            vllm_args_list.append('            - "--quantization"')
            vllm_args_list.append(f'            - "{quantization}"')
        
        env_vars_list = []
        
        if "a100" in acc_type_full or "l4" in acc_type_full:
            # A100/L4 Optimizations (Ampere/Ada Lovelace support bfloat16)
            vllm_args_list.append('            - "--dtype"')
            vllm_args_list.append('            - "bfloat16"')
            vllm_args_list.append('            - "--enable-chunked-prefill"')
        else:
            # T4 Compatibility fallback
            vllm_args_list.append('            - "--dtype"')
            vllm_args_list.append('            - "float16"')
            vllm_args_list.append('            - "--enforce-eager"')
            env_vars_list.append('            - name: VLLM_ATTENTION_BACKEND\n              value: "TORCH_SDPA"')

        vllm_args = "\n".join(vllm_args_list)
        env_vars = "\n".join(env_vars_list) if env_vars_list else ""

    content = content.replace("${IMAGE_NAME}", image_name)
    content = content.replace("${RESOURCE_LIMITS}", resource_limits)
    content = content.replace("${RESOURCE_REQUESTS}", resource_requests)
    content = content.replace("${ENV_VARS}", env_vars)
    content = content.replace("${ARGS}", vllm_args)

    return content
