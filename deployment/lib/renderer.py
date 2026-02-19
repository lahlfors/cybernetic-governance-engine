
from pathlib import Path

def generate_vllm_manifest(accelerator, config, app_name="vllm-inference"):
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

    print(f"ℹ️ Generating GPU vLLM manifest for {app_name} (Type: {acc_type_full})...")
    
    # Logic to switch image if using Run:ai Streamer
    # We need project_id from config to construct the image URI
    project_id = config.get("project", {}).get("id")
    
    # Default image
    image_name = image_gpu
    
    model_conf = config.get("model", {})
    load_format = model_conf.get("load_format")
    model_name_check = model_conf.get("name", "")
    
    if load_format == "runai_streamer" or model_name_check.startswith("gs://"):
        if project_id:
            image_name = f"gcr.io/{project_id}/vllm-streamer:latest"
            print(f"🚀 Using vLLM Streamer Image: {image_name}")
        else:
            print("⚠️ project_id not found in config, keeping default image but this might fail for streamer.")

    resource_limits = '              nvidia.com/gpu: "1"'
    resource_requests = '              nvidia.com/gpu: "1"'

    model_conf = config.get("model", {})
    model_name = model_conf.get("name", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    quantization = model_conf.get("quantization")

    tool_parser = "llama3_json"
    if "Qwen" in model_name or "DeepSeek" in model_name:
        tool_parser = "hermes"

    # Run:ai Model Streamer Configuration
    # If model is gs://, use streamer. Otherwise use standard HF loading.
    model_path = model_name
    use_streamer = False
    
    if model_path and model_path.startswith("gs://"):
        use_streamer = True
        print(f"🚀 Detected GCS path, enabling Run:ai Streamer for {model_path}")
    else:
        print(f"⚠️ Model {model_name} is not a valid gs:// path. Disabling Streamer and using standard HF loading.")
        # Ensure we don't force 'runai_streamer' if it's not a GCS path
    
    # Base settings
    vllm_args_list = [
        '            - "--model"',
        f'            - "{model_path}"',
        f'            - "--served-model-name"',
        f'            - "{config.get("model", {}).get("served_name", model_name)}"',
        '            - "--enable-auto-tool-choice"',
        '            - "--tool-call-parser"',
        f'            - "{tool_parser}"',
        '            - "--enforce-eager"',
        # '            - "--model-loader-extra-config"', # Moved to conditional below
        # '            - \'{"concurrency": 8}\'' # Tune concurrency for speed
    ]
    
    if use_streamer:
        vllm_args_list.append('            - "--load-format"')
        vllm_args_list.append('            - "runai_streamer"')
        vllm_args_list.append('            - "--model-loader-extra-config"')
        vllm_args_list.append('            - \'{"concurrency": 8}\'')
    else:
        # Standard loading (auto/safetensors)
        pass

    if quantization:
        vllm_args_list.append('            - "--quantization"')
        vllm_args_list.append(f'            - "{quantization}"')

    load_format = model_conf.get("load_format")
    if load_format and load_format != "runai_streamer": # Allow override but default to streamer if not set? 
        # actually we forced it above. 
        # If user explicitly set something else, maybe we should respect it? 
        # But we are migrating to streamer.
        pass

    extra_config = model_conf.get("extra_config")
    if extra_config:
        vllm_args_list.append('            - "--model-loader-extra-config"')
        vllm_args_list.append(f"            - '{extra_config}'")

    max_model_len = model_conf.get("max_model_len")
    if max_model_len:
        vllm_args_list.append('            - "--max-model-len"')
        vllm_args_list.append(f'            - "{max_model_len}"')

    gpu_mem_util = model_conf.get("gpu_memory_utilization")
    if gpu_mem_util:
        vllm_args_list.append('            - "--gpu-memory-utilization"')
        vllm_args_list.append(f'            - "{gpu_mem_util}"')

    max_num_seqs = model_conf.get("max_num_seqs")
    if max_num_seqs:
        vllm_args_list.append('            - "--max-num-seqs"')
        vllm_args_list.append(f'            - "{max_num_seqs}"')

    if model_conf.get("enable_prefix_caching"):
        vllm_args_list.append('            - "--enable-prefix-caching"')

    env_vars_list = [
        '            - name: HUGGING_FACE_HUB_TOKEN',
        '              valueFrom:',
        '                secretKeyRef:',
        '                  name: hf-token-secret',
        '                  key: token',
        '            - name: AWS_ACCESS_KEY_ID',
        '              valueFrom:',
        '                secretKeyRef:',
        '                  name: gcs-credentials-secret',
        '                  key: AWS_ACCESS_KEY_ID',
        '            - name: AWS_SECRET_ACCESS_KEY',
        '              valueFrom:',
        '                secretKeyRef:',
        '                  name: gcs-credentials-secret',
        '                  key: AWS_SECRET_ACCESS_KEY',
        '            - name: AWS_REGION',
        '              valueFrom:',
        '                secretKeyRef:',
        '                  name: gcs-credentials-secret',
        '                  key: AWS_REGION',
        '            - name: AWS_ENDPOINT_URL',
        '              valueFrom:',
        '                secretKeyRef:',
        '                  name: gcs-credentials-secret',
        '                  key: AWS_ENDPOINT_URL',
        '            - name: AWS_EC2_METADATA_DISABLED',
        '              value: "true"',
        '            - name: AC_LOG_VERBOSITY',
        '              value: "info"',
        '            - name: RUNAI_STREAMER_S3_USE_VIRTUAL_ADDRESSING',
        '              value: "0"'
    ]

    # Model specific optimizations
    if ("a100" in acc_type_full or "l4" in acc_type_full) and not quantization:
        # A100/L4 Optimizations (Ampere/Ada Lovelace support bfloat16)
        # AWQ often requires float16, so we skip bfloat16 if quantized
        vllm_args_list.append('            - "--dtype"')
        vllm_args_list.append('            - "bfloat16"')
        # vllm_args_list.append('            - "--enable-chunked-prefill"') # Potential conflict with streamer?
    else:
        # T4 Compatibility fallback OR AWQ fallback
        vllm_args_list.append('            - "--dtype"')
        vllm_args_list.append('            - "float16"')
        # vllm_args_list.append('            - "--enforce-eager"') # Already added above globally for streamer stability
        env_vars_list.append('            - name: VLLM_ATTENTION_BACKEND\n              value: "TORCH_SDPA"')

    vllm_args = "\n".join(vllm_args_list)
    env_vars = "\n".join(env_vars_list)

    node_selector_list = [f'        cloud.google.com/gke-accelerator: {acc_type_full}']
    node_selector = "\n".join(node_selector_list)

    # Add Pod Anti-Affinity
    # If this is vllm-inference, anti-affinity with vllm-reasoning
    # If this is vllm-reasoning, anti-affinity with vllm-inference
    affinity_target = "vllm-reasoning" if app_name == "vllm-inference" else "vllm-inference"
    
    affinity = f"""
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - {affinity_target}
            topologyKey: "kubernetes.io/hostname"
    """
    
    tolerations += "\n" + affinity
    
    print(f"DEBUG: Replacing placeholders in manifest. Image: {image_name}, App: {app_name}")

    content = content.replace("${APP_NAME}", app_name)
    content = content.replace("${IMAGE_NAME}", image_name)
    content = content.replace("${RESOURCE_LIMITS}", resource_limits)
    content = content.replace("${RESOURCE_REQUESTS}", resource_requests)
    content = content.replace("${ENV_VARS}", env_vars)
    content = content.replace("${ARGS}", vllm_args)
    content = content.replace("${NODE_SELECTOR}", node_selector)
    content = content.replace("${TOLERATIONS}", tolerations)

    return content
