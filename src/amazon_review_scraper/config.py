"""
Configuration management for the Amazon Review Scraper service.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Service configuration
    SERVICE_NAME: str = "amazon-review-scraper"
    SERVICE_VERSION: str = "0.2.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # API configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    API_PREFIX: str = ""
    CORS_ORIGINS: str = "*"
    
    # Database configuration
    REVIEWS_DB_URL: str = "sqlite:///./reviews.db"
    
    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 900  # 15 minutes
    
    # Oxylabs API configuration
    OXYSCRAPER_BASE_URL: str = "https://realtime.oxylabs.io/v1/queries"
    OXYSCRAPER_AUTH_USER: Optional[str] = None
    OXYSCRAPER_AUTH_PASS: Optional[str] = None
    
    # Rate limiting configuration
    RATE_LIMIT_RPS: float = 1.0  # Requests per second for free mode
    MAX_PAGES_FREE: int = 2  # Maximum pages to scrape in free mode
    MAX_PAGES_OXYLABS: int = 10  # Maximum pages to scrape with Oxylabs
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: int = 5
    
    # Scraping configuration
    USER_AGENTS: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    # Queue configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    TASK_TIME_LIMIT: int = 300  # 5 minutes
    TASK_SOFT_TIME_LIMIT: int = 270  # 4.5 minutes
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    @property
    def amazon_domains(self) -> dict[str, str]:
        """Mapping of domain codes to Amazon URLs."""
        return {
            "com": "https://www.amazon.com",
            "co.uk": "https://www.amazon.co.uk",
            "de": "https://www.amazon.de",
            "fr": "https://www.amazon.fr",
            "es": "https://www.amazon.es",
            "it": "https://www.amazon.it",
            "nl": "https://www.amazon.nl",
            "ca": "https://www.amazon.ca",
            "com.au": "https://www.amazon.com.au",
            "co.jp": "https://www.amazon.co.jp",
            "in": "https://www.amazon.in",
            "com.br": "https://www.amazon.com.br",
            "com.mx": "https://www.amazon.com.mx",
        }
    
    def get_amazon_url(self, asin: str, domain: str = "com") -> str:
        """Get the Amazon product URL for a given ASIN and domain."""
        base_url = self.amazon_domains.get(domain, self.amazon_domains["com"])
        return f"{base_url}/dp/{asin}"
    
    def get_reviews_url(self, asin: str, domain: str = "com", page: int = 1) -> str:
        """Get the Amazon reviews URL for a given ASIN, domain, and page."""
        base_url = self.amazon_domains.get(domain, self.amazon_domains["com"])
        return f"{base_url}/product-reviews/{asin}?pageNumber={page}"
    
    @property
    def has_oxylabs_credentials(self) -> bool:
        """Check if Oxylabs credentials are configured."""
        return bool(self.OXYSCRAPER_AUTH_USER and self.OXYSCRAPER_AUTH_PASS)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()