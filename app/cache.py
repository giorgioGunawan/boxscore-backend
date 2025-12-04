import json
from typing import Optional, Any
from datetime import datetime
from app.config import get_settings

settings = get_settings()

# In-memory cache fallback
_memory_cache: dict[str, tuple[Any, float]] = {}

# Redis connection (lazy loaded)
_redis_client = None

# Metrics tracking
cache_metrics = {
    "hits": 0,
    "misses": 0,
    "upstream_calls": 0,
    "last_reset": datetime.utcnow().isoformat(),
}


async def _get_redis():
    """Get Redis client if available."""
    global _redis_client
    
    if not settings.use_redis:
        return None
    
    if _redis_client is None:
        try:
            import redis.asyncio as redis
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await _redis_client.ping()
        except Exception as e:
            print(f"Redis not available, using in-memory cache: {e}")
            return None
    
    return _redis_client


async def get_redis():
    """Public function to get Redis client."""
    return await _get_redis()


async def close_redis():
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache (Redis or in-memory)."""
    try:
        redis = await _get_redis()
        
        if redis:
            value = await redis.get(key)
            if value:
                cache_metrics["hits"] += 1
                return json.loads(value)
        else:
            # In-memory fallback
            if key in _memory_cache:
                value, expiry = _memory_cache[key]
                if expiry > datetime.utcnow().timestamp():
                    cache_metrics["hits"] += 1
                    return value
                else:
                    del _memory_cache[key]
        
        cache_metrics["misses"] += 1
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        cache_metrics["misses"] += 1
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Set value in cache with TTL."""
    try:
        redis = await _get_redis()
        
        if redis:
            await redis.setex(key, ttl, json.dumps(value, default=str))
        else:
            # In-memory fallback
            expiry = datetime.utcnow().timestamp() + ttl
            _memory_cache[key] = (value, expiry)
        
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """Delete key from cache."""
    try:
        redis = await _get_redis()
        
        if redis:
            await redis.delete(key)
        else:
            _memory_cache.pop(key, None)
        
        return True
    except Exception as e:
        print(f"Cache delete error: {e}")
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern."""
    try:
        redis = await _get_redis()
        
        if redis:
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await redis.delete(*keys)
            return len(keys)
        else:
            # In-memory fallback - simple pattern matching
            import fnmatch
            keys_to_delete = [k for k in _memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_delete:
                del _memory_cache[k]
            return len(keys_to_delete)
    except Exception as e:
        print(f"Cache delete pattern error: {e}")
        return 0


def increment_upstream_calls():
    """Track upstream API calls."""
    cache_metrics["upstream_calls"] += 1


def get_cache_metrics() -> dict:
    """Get cache metrics."""
    total = cache_metrics["hits"] + cache_metrics["misses"]
    hit_rate = (cache_metrics["hits"] / total * 100) if total > 0 else 0
    return {
        **cache_metrics,
        "total_requests": total,
        "hit_rate_pct": round(hit_rate, 2),
        "cache_type": "redis" if settings.use_redis else "memory",
    }


def reset_cache_metrics():
    """Reset cache metrics."""
    cache_metrics["hits"] = 0
    cache_metrics["misses"] = 0
    cache_metrics["upstream_calls"] = 0
    cache_metrics["last_reset"] = datetime.utcnow().isoformat()
