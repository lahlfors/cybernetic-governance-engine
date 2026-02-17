
import os
import subprocess
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download
from dotenv import load_dotenv

load_dotenv()

# Configuration
BUCKET_NAME = "laah-cybernetics-models"
MODELS_TO_MIRROR = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    # "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    # "casperhansen/deepseek-r1-distill-llama-8b-awq" # Already done
]

def check_gsutil():
    if shutil.which("gsutil") is None:
        raise RuntimeError("gsutil not found. Please install Google Cloud SDK.")

def upload_to_gcs(local_path: Path, gcs_path: str):
    print(f"🚀 Uploading {local_path} to {gcs_path}...")
    # Use -m for parallel upload, -o for composite upload optimization
    # check if crcmod is installed for speed? User said to pip install crcmod.
    # We'll just run the command.
    cmd = [
        "gsutil", "-o", "GSUtil:parallel_composite_upload_threshold=150M",
        "-m", "cp", "-r", f"{local_path}/*", gcs_path
    ]
    subprocess.check_call(cmd)
    print(f"✅ Uploaded to {gcs_path}")

def mirror_models():
    check_gsutil()
    
    # Ensure HF transfer is enabled for speed
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    
    # Check for token
    if not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        print("⚠️ HUGGING_FACE_HUB_TOKEN not found in env. Gated models (Llama 3.1) might fail.")
    
    work_dir = Path("temp_model_mirror")
    work_dir.mkdir(exist_ok=True)
    
    try:
        for model_id in MODELS_TO_MIRROR:
            print(f"\n--- ⬇️ Processing {model_id} ---")
            
            # 1. Download from HF
            local_model_dir = work_dir / model_id.replace("/", "--")
            print(f"📥 Downloading to {local_model_dir}...")
            
            try:
                snapshot_download(
                    repo_id=model_id,
                    local_dir=local_model_dir,
                    ignore_patterns=["*.msgpack", "*.h5", "*.ot"],
                    local_dir_use_symlinks=False # Important for gsutil to copy actual files
                )
            except Exception as e:
                print(f"❌ Download failed for {model_id}: {e}")
                continue

            # 2. Upload to GCS
            gcs_path = f"gs://{BUCKET_NAME}/{model_id}"
            
            # Check if already exists? (Optional, gsutil cp -n can skip existing)
            # For now, just overwrite/update
            try:
                upload_to_gcs(local_model_dir, gcs_path)
            except Exception as e:
                print(f"❌ Upload failed for {model_id}: {e}")
                continue
                
            # 3. Cleanup to save space
            print(f"🧹 Cleaning up {local_model_dir}...")
            shutil.rmtree(local_model_dir)
            
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)
            print("✨ Temporary directory cleaned up.")

if __name__ == "__main__":
    mirror_models()
