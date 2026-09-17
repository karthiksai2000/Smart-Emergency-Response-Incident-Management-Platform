"""Application configuration and environment settings."""

import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env values take precedence
load_dotenv(override=True)


class Settings(BaseSettings):
    """Configuration loaded from environment variables or .env file."""

    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-flash-latest"

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_INPUT_TOPIC: str = "incident.created"
    KAFKA_OUTPUT_TOPIC: str = "incident.analyzed"
    KAFKA_CONSUMER_GROUP: str = "ai-service"
    KAFKA_ENABLED: bool = True
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_POLL_TIMEOUT_SECONDS: float = 1.0

    # Application Configuration
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
