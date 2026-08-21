from redis.asyncio import Redis
from fastapi import FastAPI
from typing import Optional
from apps.backend.core.config import settings


class RedisManager:
    def __init__(self):
        self.redis: Optional[Redis] = None
        self.ready: bool = False
        self.last_error: Optional[str] = None

    async def init_redis_pool(self, app: FastAPI):
        """在FastAPI应用启动时初始化Redis连接池"""
        # 构建 Redis URL
        redis_url = (f"redis://:{settings.REDIS_PASSWORD}@"
                     f"{settings.REDIS_HOST}:{settings.REDIS_PORT}")

        self.redis = Redis.from_url(
            redis_url,
            decode_responses=True  # 替换原来的 encoding="utf-8"
        )

        # 测试连接
        try:
            await self.redis.ping()
        except Exception:
            self.last_error = "redis_unavailable"
            self.ready = False
            await self.redis.aclose()
            self.redis = None
            return False
        self.ready = True
        self.last_error = None
        return True

    async def check_readiness(self) -> bool:
        """主动检查连接，供 readiness 使用；失败不会伪造健康状态。"""
        if self.redis is None:
            # A failed ping closes the client below.  The next probe may
            # establish a fresh connection, so a transient Redis outage does
            # not require an application restart to recover readiness.
            await self.init_redis_pool(None)
            return self.ready
        try:
            await self.redis.ping()
        except Exception:
            self.last_error = "redis_unavailable"
            self.ready = False
            try:
                await self.redis.aclose()
            finally:
                self.redis = None
            return False
        self.last_error = None
        self.ready = True
        return True

    async def get(self, key: str) -> Optional[str]:
        """从Redis获取值"""
        if self.redis is not None:
            return await self.redis.get(key)
        return None

    async def set(self, key: str, value: str, expire: int = None) -> bool:
        """设置Redis键值对"""
        if self.redis is not None:
            await self.redis.set(key, value, ex=expire)
            return True
        return False

    async def delete(self, key: str) -> int:
        """删除Redis键"""
        if self.redis is not None:
            return await self.redis.delete(key)
        return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if self.redis is not None:
            return await self.redis.exists(key) > 0
        return False

    async def increment(self, key: str) -> int:
        """增加键的值"""
        if self.redis is not None:
            return await self.redis.incr(key)
        return 0

    async def close_redis_pool(self):
        """关闭Redis连接"""
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None  # 关闭后置为 None
        self.ready = False
