from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/luka"  # pragma: allowlist secret
    )
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""  # Supabase Dashboard > Settings > API > JWT Secret
    redis_url: str = "redis://localhost:6379"
    pubsub_audience: str = ""
    outlook_client_state: str = "dev-secret"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""  # Google AI Studio API key
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = ""  # Comma-separated additional CORS origins
    environment: str = "development"
    gcp_project_id: str = "luka-project"
    token_encryption_key: str = ""  # Fernet key for encrypting OAuth tokens at rest
    gmail_pubsub_topic: str = "luka-gmail-notifications"
    google_client_id: str = ""
    google_client_secret: str = ""

    # SMTP Settings (legacy — prefer Resend)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Resend (transactional email via HTTP API)
    resend_api_key: str = ""

    # Luka Connect (bank scraper service)
    connect_encryption_key: str = ""  # 32-byte hex key for AES-256-GCM
    luka_connect_url: str = "http://localhost:3001"
    luka_connect_api_key: str = ""
    backend_public_url: str = "http://localhost:8000"  # Used for webhook callback URLs


settings = Settings()
