from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/luka"  # pragma: allowlist secret
    )
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
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

    # LLM parser waterfall thresholds (confidence scores)
    llm_waterfall_thresholds: str = "0.9,0.8,0.7,0.0"
    llm_shadow_validation_rate: float = 0.25
    template_agent_min_emails: int = 20
    template_agent_recency_days: int = 14
    template_agent_recency_min: int = 5

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

    # Plaid (US bank connections)
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # "sandbox" or "production"


settings = Settings()
