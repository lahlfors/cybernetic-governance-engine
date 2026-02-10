
import asyncio
import os
from langgraph.checkpoint.redis import AsyncRedisSaver

async def probe():
    print(f"AsyncRedisSaver methods: {dir(AsyncRedisSaver)}")
    
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    saver = AsyncRedisSaver.from_conn_string(redis_url)
    print(f"Saver instance methods: {dir(saver)}")

if __name__ == "__main__":
    asyncio.run(probe())
