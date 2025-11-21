from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://genealogy_user:genealogy_pass@localhost:5432/genealogy_db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # DeepSeek API Key for AI file conversion
    deepseek_api_key: str = "your_api_key_here"

    # Matching thresholds
    name_match_threshold: float = 0.85
    auto_merge_threshold: float = 0.90
    manual_review_threshold: float = 0.70
    date_proximity_years: int = 2

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings():
    return Settings()
