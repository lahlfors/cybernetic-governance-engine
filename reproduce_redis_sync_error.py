
from langgraph.checkpoint.redis import AsyncRedisSaver

def main():
    redis_url = "redis://localhost:6379"
    print(f"Creating AsyncRedisSaver with {redis_url} (Sync context)")
    try:
        # This is expected to fail if it requires a loop immediately
        saver = AsyncRedisSaver(redis_url=redis_url)
        print("Successfully created AsyncRedisSaver")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
