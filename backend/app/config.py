import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    resend_api_key: str = ""
    email_from: str = "noreply@vizy.com.br"
    auth_alert_email: str = ""
    auth_alert_from: str = ""
    auth_alert_signup_enabled: bool = True
    auth_alert_login_enabled: bool = False
    secret_key: str = "change-me-in-production"
    admin_api_key: str = ""
    admin_email: str = "oagcoliveira@gmail.com"
    access_token_expire_minutes: int = 10080  # 7 days

    class Config:
        env_file = ".env"


settings = Settings()


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "").lower() in {"prod", "production"} or bool(
        os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("VERCEL")
    )


if _is_production() and (
    settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32
):
    raise RuntimeError(
        "Unsafe SECRET_KEY: set a strong random SECRET_KEY before running in production."
    )
