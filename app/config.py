from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database - defaults to SQLite for easy local development
    database_url: str = "sqlite:///./boxscore.db"
    
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
