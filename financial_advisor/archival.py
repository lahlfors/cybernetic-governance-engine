import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone

from google.cloud import storage
from redis import Redis
from langgraph.checkpoint.redis import RedisSaver

# Configure Logging
logger = logging.getLogger("ArchivalWorker")
logger.setLevel(logging.INFO)

class ArchivalService:
    def __init__(self, redis_url: str, gcs_bucket_name: str, project_id: str):
        self.redis_client = Redis.from_url(redis_url)
        self.checkpointer = RedisSaver(conn=self.redis_client)

        # GCS Client
        try:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = self.storage_client.bucket(gcs_bucket_name)
        except Exception as e:
            logger.warning(f"⚠️ GCS Client Init Failed: {e}. Archival will fail.")
            self.bucket = None

    def archive_thread(self, thread_id: str):
        """
        Reads thread state from Redis, persists to GCS, and deletes from Redis.
        """
        if not self.bucket:
            logger.error("❌ No GCS bucket configured.")
            return

        logger.info(f"📦 Archiving Thread: {thread_id}")

        # 1. Retrieve State
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = self.checkpointer.get(config)

        if not checkpoint:
            logger.warning(f"⚠️ No checkpoint found for {thread_id}")
            return

        # 2. Serialize
        try:
            data_to_archive = {
                "thread_id": thread_id,
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "checkpoint": checkpoint
            }
            json_data = json.dumps(data_to_archive, default=str)

        except Exception as e:
            logger.error(f"❌ Serialization Failed: {e}")
            return

        # 3. Write to GCS (WORM style naming)
        date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        blob_name = f"archived_threads/{date_prefix}/{thread_id}.jsonl"

        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(json_data, content_type="application/json")
            logger.info(f"✅ Uploaded to gs://{self.bucket.name}/{blob_name}")
        except Exception as e:
            logger.error(f"❌ GCS Upload Failed: {e}")
            return

        # 4. Cleanup Redis
        try:
            cursor = '0'
            # Loop manual scan. Note: Redis scan returns (cursor, keys).
            # When cursor returns to 0 (or '0'), iteration ends.
            # Python redis client handles type conversion usually but explicit check is good.

            # Initial call
            cursor, keys = self.redis_client.scan(cursor=0, match=f"*{thread_id}*", count=100)
            if keys:
                self.redis_client.delete(*keys)

            while str(cursor) != '0' and cursor != 0:
                cursor, keys = self.redis_client.scan(cursor=cursor, match=f"*{thread_id}*", count=100)
                if keys:
                    self.redis_client.delete(*keys)

            logger.info(f"🗑️ Cleanup complete for {thread_id}")
        except Exception as e:
            logger.error(f"⚠️ Redis Cleanup Failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--redis-url", default="redis://localhost:6379")
    args = parser.parse_args()

    service = ArchivalService(args.redis_url, args.bucket, args.project)
    service.archive_thread(args.thread_id)
