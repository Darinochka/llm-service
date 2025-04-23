from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    REDIS_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    TELEGRAM_BOT_TOKEN: str

    VLLM_API_URL: str
    VLLM_MODEL_NAME: str = "default"

    SUBSCRIPTION_PRICE_RUB: float = 5.0
    SUBSCRIPTION_DURATION_MIN: int = 1
    API_URL: str

    class Config:
        env_file = ".env"

settings = Settings() 