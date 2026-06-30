from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    KV_REST_API_URL: str = ""
    KV_REST_API_TOKEN: str = ""
    PRIMARY_BACKEND_URL: str = "http://localhost:8001"
    CONTROLLER_API_KEY: str = ""
    DISCORD_OAuth2_MANNUAL_LOGIN_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
