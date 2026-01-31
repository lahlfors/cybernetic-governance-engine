try:
    from langgraph.checkpoint.redis import RedisSaver
    print("RedisSaver attributes:", dir(RedisSaver))
except ImportError as e:
    print("ImportError:", e)

try:
    from langgraph.checkpoint.redis import AsyncRedisSaver
    print("AsyncRedisSaver available!")
except ImportError:
    print("AsyncRedisSaver NOT available")
