import redis.asyncio as redis

from app.core.config import settings


redis_client = redis.from_url(
    settings.REDIS_CONNECTION_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis():
    return redis_client