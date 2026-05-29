from redis import ConnectionPool, Redis

from core.config import Settings, get_settings


def create_redis_client(settings: Settings | None = None) -> Redis:
    resolved = settings or get_settings()
    pool = ConnectionPool.from_url(
        resolved.redis_url,
        decode_responses=True,
        max_connections=resolved.redis_connection_pool_size,
        socket_connect_timeout=resolved.redis_publish_timeout_seconds,
        socket_timeout=resolved.redis_publish_timeout_seconds,
    )
    return Redis(connection_pool=pool)
