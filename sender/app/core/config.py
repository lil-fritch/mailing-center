from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "MailingSender"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path("logs/mailing_sender.log")

    # Selenium settings
    SELENIUM_COOKIES_DIR: Path = Path("selenium_data/cookies")
    SELENIUM_DOWNLOAD_DIR: Path = Path("selenium_data/downloads")
    SELENIUM_CHROME_BINARY: Optional[str] = None  # Path to Chrome/Chromium binary (e.g., "/usr/bin/google-chrome" or "/usr/bin/chromium-browser")

    # History storage
    EMAIL_HISTORY_FILE: Path = Path("config/email_history.json")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() 