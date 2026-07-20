import hashlib
import logging
import pickle
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    from redis import Redis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover
    Redis = None
    RedisError = Exception

from config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Multi-layer cache with memory, Redis, and optional database-backed fallback."""

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        database_backend: Optional[Any] = None,
        ttl_seconds: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
    ) -> None:
        self.redis_client = redis_client
        self.database_backend = database_backend
        if self.redis_client is None and Redis is not None:
            try:
                self.redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
                self.redis_client.ping()
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis unavailable; continuing without Redis cache: %s", exc)
                self.redis_client = None
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
        }
        self._ttl_seconds = ttl_seconds or settings.CACHE_TTL_SECONDS
        self._max_size_bytes = max_size_bytes or settings.MAX_CACHE_SIZE_BYTES
        self._current_size_bytes = 0
        self._last_cleanup = datetime.utcnow()

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _serialize(self, value: Any) -> bytes:
        return pickle.dumps(value)

    def _deserialize(self, payload: bytes) -> Any:
        return pickle.loads(payload)

    def _estimate_size(self, value: Any) -> int:
        try:
            return len(self._serialize(value))
        except Exception:
            return 1024

    def _is_expired(self, item: Dict[str, Any]) -> bool:
        expires_at = item.get("expires_at")
        if not expires_at:
            return False
        return datetime.utcnow() >= expires_at

    def _prune_expired(self) -> None:
        expired_keys = []
        for key, item in list(self._memory_cache.items()):
            if self._is_expired(item):
                expired_keys.append(key)
        for key in expired_keys:
            item = self._memory_cache.pop(key, None)
            if item:
                self._current_size_bytes = max(0, self._current_size_bytes - int(item.get("size", 0)))
        self._last_cleanup = datetime.utcnow()

    def _enforce_size_limit(self) -> None:
        self._prune_expired()
        while self._current_size_bytes > self._max_size_bytes and self._memory_cache:
            self._memory_cache.popitem(last=False)
            self._stats["evictions"] += 1
            self._current_size_bytes = max(0, self._current_size_bytes - 1024)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        with self._lock:
            cache_key = self._hash_key(key)
            ttl = ttl_seconds or self._ttl_seconds
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            size = self._estimate_size(value)
            item = {
                "value": value,
                "expires_at": expires_at,
                "size": size,
                "created_at": datetime.utcnow(),
            }
            self._memory_cache[cache_key] = item
            self._memory_cache.move_to_end(cache_key)
            self._current_size_bytes += size
            self._stats["sets"] += 1
            self._enforce_size_limit()
            if self.redis_client:
                try:
                    self.redis_client.setex(cache_key, ttl, self._serialize(value))
                except RedisError as exc:
                    logger.warning("Redis set failed: %s", exc)
            if self.database_backend and hasattr(self.database_backend, "set"):
                try:
                    self.database_backend.set(cache_key, value, ttl)
                except Exception as exc:
                    logger.warning("Database cache set failed: %s", exc)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            cache_key = self._hash_key(key)
            item = self._memory_cache.get(cache_key)
            if item and not self._is_expired(item):
                self._memory_cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                return item["value"]

            self._stats["misses"] += 1
            if self.redis_client:
                try:
                    payload = self.redis_client.get(cache_key)
                    if payload:
                        value = self._deserialize(payload)
                        self._memory_cache[cache_key] = {
                            "value": value,
                            "expires_at": datetime.utcnow() + timedelta(seconds=self._ttl_seconds),
                            "size": self._estimate_size(value),
                            "created_at": datetime.utcnow(),
                        }
                        self._memory_cache.move_to_end(cache_key)
                        self._stats["hits"] += 1
                        return value
                except RedisError as exc:
                    logger.warning("Redis read failed: %s", exc)
            if self.database_backend and hasattr(self.database_backend, "get"):
                try:
                    value = self.database_backend.get(cache_key)
                    if value is not None:
                        self._memory_cache[cache_key] = {
                            "value": value,
                            "expires_at": datetime.utcnow() + timedelta(seconds=self._ttl_seconds),
                            "size": self._estimate_size(value),
                            "created_at": datetime.utcnow(),
                        }
                        self._memory_cache.move_to_end(cache_key)
                        self._stats["hits"] += 1
                        return value
                except Exception as exc:
                    logger.warning("Database cache read failed: %s", exc)
            return None

    def delete(self, key: str) -> None:
        with self._lock:
            cache_key = self._hash_key(key)
            self._memory_cache.pop(cache_key, None)
            self._stats["deletes"] += 1
            if self.redis_client:
                try:
                    self.redis_client.delete(cache_key)
                except RedisError as exc:
                    logger.warning("Redis delete failed: %s", exc)

    def clear(self) -> None:
        with self._lock:
            self._memory_cache.clear()
            self._current_size_bytes = 0
            if self.redis_client:
                try:
                    self.redis_client.flushdb()
                except RedisError as exc:
                    logger.warning("Redis flush failed: %s", exc)

    def get_health(self) -> Dict[str, Any]:
        with self._lock:
            hit_rate = 0.0
            total_requests = self._stats["hits"] + self._stats["misses"]
            if total_requests:
                hit_rate = round(self._stats["hits"] / total_requests, 4)
            return {
                "status": "healthy",
                "memory_entries": len(self._memory_cache),
                "current_size_bytes": self._current_size_bytes,
                "max_size_bytes": self._max_size_bytes,
                "hit_rate": hit_rate,
                "stats": dict(self._stats),
                "last_cleanup": self._last_cleanup.isoformat(),
            }


cache_manager = CacheManager()
