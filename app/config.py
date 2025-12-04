from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database - defaults to SQLite for easy local development
    database_url: str = "sqlite:///./boxscore.db"
    
    # Redis - optional, will use in-memory cache if not available
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False  # Set to True when Redis is available
    
    # Cache TTLs (in seconds)
    cache_ttl_games: int = 3600
    cache_ttl_standings: int = 1800
    cache_ttl_player_stats: int = 3600
    cache_ttl_player_game: int = 900
    
    # Current NBA Season
    current_season: str = "2025-26"
    current_season_type: str = "Regular Season"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
