import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

try:
    load_dotenv(override=False)
except Exception:
    pass


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "floatchat")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password123")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:password123@localhost:5432/floatchat",
    )

    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", str(24 * 60 * 60)))
    MAX_CACHE_SIZE_GB: int = int(os.getenv("MAX_CACHE_SIZE_GB", "5"))
    MAX_CACHE_SIZE_BYTES: int = int(os.getenv("MAX_CACHE_SIZE_BYTES", str(5 * 1024 * 1024 * 1024)))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

    PRE_CACHED_REGIONS: List[str] = field(
        default_factory=lambda: [
            "Arabian_Sea",
            "Bay_of_Bengal",
            "Indian_Ocean",
            "South_Atlantic",
            "North_Pacific",
        ]
    )

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s %(message)s")

    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
