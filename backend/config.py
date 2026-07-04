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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
