from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./buyerhunter.db"
    gemini_api_key: str = ""
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    max_concurrent_requests: int = 16
    download_delay: int = 2
    playwright_browser_type: str = "chromium"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    # ── Worker Pool ──
    worker_concurrency: int = 8
    worker_poll_interval: float = 1.0
    worker_queue_batch_size: int = 5

    # ── Rate Limiting ──
    rate_limit_requests_per_domain: int = 3
    rate_limit_window_seconds: int = 60
    rate_limit_token_bucket_capacity: int = 5
    rate_limit_token_refill_rate: float = 1.0

    # ── Retry ──
    retry_max_attempts: int = 3
    retry_base_delay_seconds: float = 5.0
    retry_max_delay_seconds: float = 300.0
    retry_jitter_factor: float = 0.25

    # ── Proxy ──
    proxy_enabled: bool = False
    proxy_list: str = ""
    proxy_backconnect_url: str = ""
    proxy_backconnect_api_key: str = ""
    proxy_rotation_strategy: str = "round-robin"

    # ── HTTP Client ──
    http_request_timeout: int = 30
    http_max_redirects: int = 5
    http_verify_ssl: bool = True

    # ── Robots.txt ──
    robots_cache_ttl: int = 3600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
