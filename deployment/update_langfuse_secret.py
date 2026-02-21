
import subprocess
import json
import sys
import os

def run_command(cmd, capture_output=True):
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=capture_output, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(e.stderr)
        raise

def main():
    project_id = "laah-cybernetics"
    secret_name = "langfuse-database-url"
    instance_name = "langfuse-instance-laah-cybernetics"
    
    print("⏳ Fetching SQL Instance Private IP...")
    try:
        instance_json = run_command(f"gcloud sql instances describe {instance_name} --project={project_id} --format=json")
        instance_data = json.loads(instance_json)
        ip_addresses = instance_data.get("ipAddresses", [])
        private_ip = next((ip["ipAddress"] for ip in ip_addresses if ip["type"] == "PRIVATE"), None)
        
        if not private_ip:
            print("❌ No Private IP found for instance.")
            # Check if operation is still running
            print("Checking operations...")
            ops = run_command(f"gcloud sql operations list --instance={instance_name} --limit=1 --filter='status=RUNNING' --format='value(name)'")
            if ops:
                print(f"⚠️ Operation {ops} is still running. Please wait.")
            sys.exit(1)
            
        print(f"✅ Found Private IP: {private_ip}")
        
        print("⏳ Fetching existing connection string from Secret Manager...")
        conn_string = run_command(f"gcloud secrets versions access latest --secret={secret_name} --project={project_id}")
        
        # Parse connection string to get user/pass
        # Format: postgresql://USER:PASS@HOST/DB...
        # We assume standard format
        if "@" in conn_string and "postgresql://" in conn_string:
            parts = conn_string.split("@")
            user_pass = parts[0].replace("postgresql://", "")
            if ":" in user_pass:
                username, password = user_pass.split(":")
                
                new_conn_string = f"postgresql://{username}:{password}@{private_ip}:5432/langfuse"
                print(f"🔑 Constructed new DATABASE_URL: {new_conn_string}")
                
                print("🚀 Updating advisor-secrets in Kubernetes...")
                # We update the secret
                # We need to preserve other keys, but apply only this one? 
                # kubectl create secret generic ... --dry-run=client -o yaml | kubectl apply -f - 
                # works if we want to replace/add. But we want to PATCH if it exists?
                # Actually apply will merge if we provide the full object, but here we only provide one key?
                # No, create secret generic will create a NEW object with ONLY that key if we pipe to apply.
                # We should use 'kubectl patch' or just recreate it with all keys if possible, but we don't know all keys easily without reading them.
                # EASIEST: Read existing secret, update key, apply.
                
                secret_json = run_command("kubectl get secret advisor-secrets -n governance-stack -o json", capture_output=True)
                secret_data = json.loads(secret_json)
                import base64
                
                encoded_url = base64.b64encode(new_conn_string.encode()).decode()
                secret_data["data"]["DATABASE_URL"] = encoded_url
                
                # Write to temp file and apply
                with open("temp_secret.json", "w") as f:
                    json.dump(secret_data, f)
                
                run_command("kubectl apply -f temp_secret.json")
                os.remove("temp_secret.json")
                print("✅ Secret updated successfully.")
                
                # Restart pods
                print("🔄 Restarting langfuse-web and langfuse-worker...")
                run_command("kubectl delete pod -l app=langfuse-web -n governance-stack")
                run_command("kubectl delete pod -l app=langfuse-worker -n governance-stack")
                print("✅ Pods restarted.")
                
            else:
                print("❌ Could not parse username/password from connection string.")
        else:
            print("❌ Invalid connection string format.")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
