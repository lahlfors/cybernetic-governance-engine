
import asyncio
from langgraph.checkpoint.redis import AsyncRedisSaver

async def main():
    redis_url = "redis://localhost:6379"
    # Simulating what might happen if called outside of a running loop or in a way that checks for it
    print(f"Creating AsyncRedisSaver with {redis_url}")
    try:
        saver = AsyncRedisSaver(redis_url=redis_url)
        print("Successfully created AsyncRedisSaver")
        # Try to use it to ensure it works
        async with saver:
             print("Saver context manager entered")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
