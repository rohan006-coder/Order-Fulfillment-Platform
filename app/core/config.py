from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Order Fulfillment Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./order_fulfillment.db"
    secret_key: str = "super-secret-production-key-999#"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
