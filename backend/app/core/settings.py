from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_assistant_id_mail_generator: str | None = None
    openai_assistant_id_answer_generator: str | None = None
    openai_api_key: str | None = None

    mail_api_url: str | None = None
    mail_api_url_2: str | None = None
    mail_api_base_url: str | None = None
    mail_api_key: str | None = None
    mail_api_endpoint: str = "/email/send"  # Default endpoint path

    email_pause_seconds: float = 1.0
    campaign_from_emails: list[str] = []
    email_pause_min_seconds: float | None = None
    email_pause_max_seconds: float | None = None
    sender_accounts_file: str | None = "app/config/sender_accounts.json"
    sender_accounts_file_2: str | None = "app/config/sender_accounts_2.json"

    # Campaign work hours (local time in campaign timezone)
    campaign_work_start_hour: int = 9
    campaign_work_end_hour: int = 18

    parallel_key: str = None
    
    # Database settings
    database_url: str = "postgresql://user:password@localhost:5432/mailing_center?client_encoding=utf8&application_name=mailing_center"
    database_echo: bool = False

    # Development mode: when True, do not actually send emails, just log to console
    development_mode: bool = False
    
    # IMAP settings
    imap_thread_pool_size: int = 4  # Number of threads for parallel IMAP polling
    
    # Site password protection
    site_password: str | None = None

    # JWT settings for the dashboard API
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 12
    
    # Database password for import operations
    db_password: str | None = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()