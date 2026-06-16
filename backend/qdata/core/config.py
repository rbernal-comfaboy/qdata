from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://qdata:qdata_pass@localhost:5432/qdata"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "qdata@tudominio.com"
    env: str = "development"
    log_level: str = "INFO"
    scheduler_timezone: str = "America/Mexico_City"

    model_config = {"env_prefix": "qdata_", "env_file": ".env"}


settings = Settings()
