
import asyncio
from langgraph.checkpoint.redis import AsyncRedisSaver
from redis.asyncio import Redis as AsyncRedis

async def main():
    redis_url = "redis://localhost:6379"
    try:
        conn = AsyncRedis.from_url(redis_url, decode_responses=True)
        print(f"Created connection: {conn}")
        saver = AsyncRedisSaver(conn)
        print("Successfully created AsyncRedisSaver with connection")
    except Exception as e:
        print(f"Error with connection: {e}")

    try:
        saver = AsyncRedisSaver(redis_url)
        print("Successfully created AsyncRedisSaver with URL string")
    except Exception as e:
        print(f"Error with URL: {e}")

if __name__ == "__main__":
    asyncio.run(main())
