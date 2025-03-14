from redis.asyncio import Redis

class RedisClient:
    def __init__(self, url):
        self.client = Redis.from_url(url)

    async def get(self, key: str):
        return await self.client.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        await self.client.setex(key, ttl, value)

    async def hget(self, key: str, field: str):
        return await self.client.hget(key, field)

    async def hset(self, key: str, field: str, value: str):
        await self.client.hset(key, field, value)

    async def expire(self, key: str, ttl: int):
        await self.client.expire(key, ttl)
