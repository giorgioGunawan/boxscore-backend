from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database - defaults to SQLite for easy local development
    database_url: str = "sqlite:///./boxscore.db"
    
    # Redis - optional, will use in-memory cache if not available
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False  # Set to True when Redis is available
    
    # Cache TTLs (in seconds)
    cache_ttl_games: int = 345600  # 96 hours (4 days) - schedules don't change often
    cache_ttl_standings: int = 10800  # 3 hours - standings update after games
    cache_ttl_player_stats: int = 172800  # 48 hours (2 days) - season averages change slowly
    cache_ttl_player_game: int = 7200  # 2 hours - last game updates frequently
    cache_ttl_last_results: int = 10800  # 3 hours - last results update after games
    
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
