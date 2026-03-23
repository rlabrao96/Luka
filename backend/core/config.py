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
    fintoc_api_key: str = ""
    openai_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = ""  # Comma-separated additional CORS origins
    environment: str = "development"
    gcp_project_id: str = "luka-project"

    # SMTP Settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()
