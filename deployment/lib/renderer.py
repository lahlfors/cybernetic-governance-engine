
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
    image_gpu = vllm_conf.get("image_gpu", "vllm/vllm-openai:latest")

    node_selector = ""
    tolerations = ""

    # GPU Logic (Standard)
    acc_type_full = cluster_acc.get("type", "nvidia-tesla-t4")

    print(f"ℹ️ Generating GPU vLLM manifest (Type: {acc_type_full})...")
    image_name = image_gpu
    resource_limits = '              nvidia.com/gpu: "1"'
    resource_requests = '              nvidia.com/gpu: "1"'

    model_conf = config.get("model", {})
    model_name = model_conf.get("name", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    quantization = model_conf.get("quantization")

    tool_parser = "llama3_json"
    if "Qwen" in model_name or "DeepSeek" in model_name:
        tool_parser = "hermes"

    # Base settings
    vllm_args_list = [
        '            - "--model"',
        f'            - "{model_name}"',
        f'            - "--served-model-name"',  # Fixed duplicate arg key
        f'            - "{model_name}"',
        '            - "--enable-auto-tool-choice"',
        '            - "--tool-call-parser"',
        f'            - "{tool_parser}"'
    ]

    if quantization:
        vllm_args_list.append('            - "--quantization"')
        vllm_args_list.append(f'            - "{quantization}"')

    load_format = model_conf.get("load_format")
    if load_format:
        vllm_args_list.append('            - "--load-format"')
        vllm_args_list.append(f'            - "{load_format}"')

    max_model_len = model_conf.get("max_model_len")
    if max_model_len:
        vllm_args_list.append('            - "--max-model-len"')
        vllm_args_list.append(f'            - "{max_model_len}"')

    gpu_mem_util = model_conf.get("gpu_memory_utilization")
    if gpu_mem_util:
        vllm_args_list.append('            - "--gpu-memory-utilization"')
        vllm_args_list.append(f'            - "{gpu_mem_util}"')

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

    node_selector_list = [f'        cloud.google.com/gke-accelerator: {acc_type_full}']
    node_selector = "\n".join(node_selector_list)

    content = content.replace("${IMAGE_NAME}", image_name)
    content = content.replace("${RESOURCE_LIMITS}", resource_limits)
    content = content.replace("${RESOURCE_REQUESTS}", resource_requests)
    content = content.replace("${ENV_VARS}", env_vars)
    content = content.replace("${ARGS}", vllm_args)
    content = content.replace("${NODE_SELECTOR}", node_selector)
    # Add Pod Anti-Affinity to avoid sharing node with vllm-reasoning
    affinity = """
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - vllm-reasoning
            topologyKey: "kubernetes.io/hostname"
    """
    
    # We need to inject this into the template. 
    # The current template uses ${TOLERATIONS} and ${NODE_SELECTOR}.
    # Let's append it to specs or replace a placeholder if exists. 
    # The template (vllm-deployment.yaml.tpl) doesn't have an ${AFFINITY} placeholder.
    # It has:
    #       nodeSelector:
    # ${NODE_SELECTOR}
    #       tolerations:
    # ${TOLERATIONS}
    
    # We can inject it after tolerations. 
    # But strictly speaking, we should just insert it.
    # Let's append it to tolerations variable if we can't change template easily, 
    # OR better: Add ${AFFINITY} to template and renderer.
    
    # Quick fix: Append to tolerations string since it's just indented text injection in the template
    # Warning: Tolerations is at the end of spec. 
    
    # Let's inspect the template again.
    # It ends with:
    #       tolerations:
    # ${TOLERATIONS}
    
    # So if we append affinity text to tolerations, it might work if indentation is correct.
    # tolerations block indentation is 6 spaces? No, 8 spaces?
    # Spec is 6 spaces.
    # Layout:
    # spec:
    #   template:
    #     spec:
    #       metrics...
    #       nodeSelector: ...
    #       tolerations:
    # ${TOLERATIONS}
    
    # If I add affinity, I need to add it at `spec.template.spec` level.
    # Replacing ${TOLERATIONS} with "tolerations content\n      affinity: ..." might work.
    
    tolerations += "\n" + affinity
    
    content = content.replace("${IMAGE_NAME}", image_name)
    content = content.replace("${RESOURCE_LIMITS}", resource_limits)
    content = content.replace("${RESOURCE_REQUESTS}", resource_requests)
    content = content.replace("${ENV_VARS}", env_vars)
    content = content.replace("${ARGS}", vllm_args)
    content = content.replace("${NODE_SELECTOR}", node_selector)
    content = content.replace("${TOLERATIONS}", tolerations)

    return content
