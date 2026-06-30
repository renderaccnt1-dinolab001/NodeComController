from upstash_redis import Redis
from app.core.config import settings

# Initialize the Redis client using the REST API credentials
redis = None
if settings.KV_REST_API_URL and settings.KV_REST_API_TOKEN:
    redis = Redis(
        url=settings.KV_REST_API_URL, 
        token=settings.KV_REST_API_TOKEN
    )

class StorageService:
    @staticmethod
    def save_data(key: str, value: str):
        if not redis:
            print(f"Mock KV Save (Redis not configured): {key}")
            return
        redis.set(key, value)
        
    @staticmethod
    def get_data(key: str) -> str | None:
        if not redis:
            print(f"Mock KV Get (Redis not configured): {key}")
            return None
        return redis.get(key)
