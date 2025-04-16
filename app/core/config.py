from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis
    REDIS_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Telegram
    TELEGRAM_BOT_TOKEN: str

    # vLLM
    VLLM_API_URL: str
    VLLM_MODEL_NAME: str = "default"

    # Subscription
    SUBSCRIPTION_PRICE_RUB: float = 5.0
    SUBSCRIPTION_DURATION_DAYS: int = 30

    class Config:
        env_file = ".env"

settings = Settings() 