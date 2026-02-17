import os
import sys
from huggingface_hub import snapshot_download
from google.cloud import storage
import glob

def upload_directory_to_gcs(local_path, bucket_name, gcs_path):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    for local_file in glob.glob(local_path + '/**/*', recursive=True):
        if not os.path.isfile(local_file):
            continue
            
        # Calculate relative path
        rel_path = os.path.relpath(local_file, local_path)
        blob_path = os.path.join(gcs_path, rel_path)
        
        blob = bucket.blob(blob_path)
        print(f"Uploading {local_file} to gs://{bucket_name}/{blob_path}...")
        blob.upload_from_filename(local_file)

def main():
    model_id = os.environ.get("MODEL_ID")
    bucket_name = os.environ.get("GCS_BUCKET")
    
    if not model_id or not bucket_name:
        print("Error: MODEL_ID and GCS_BUCKET env vars required")
        sys.exit(1)
        
    print(f"Downloading {model_id} from HF...")
    # Download to local ephemeral storage
    local_dir = snapshot_download(repo_id=model_id)
    print(f"Downloaded to {local_dir}")
    
    print(f"Uploading to gs://{bucket_name}/{model_id}...")
    upload_directory_to_gcs(local_dir, bucket_name, model_id)
    print("Done!")

if __name__ == "__main__":
    main()
