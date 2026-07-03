from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    KV_REST_API_URL: str = ""
    KV_REST_API_TOKEN: str = ""
    PRIMARY_BACKEND_URL: str = "https://nodecomnetwork.dinolab001.dpdns.org"
    CONTROLLER_API_KEY: str = ""
    DISCORD_OAuth2_MANNUAL_LOGIN_WEBHOOK_URL: str = ""
    ENGINEER_JWT_SECRET: str = "change-me-in-production"

    # Supabase (PostgreSQL) credentials.
    # Set these as environment variables in Render / your deployment platform.
    # Locally, add them to the .env file.
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_HOST: str = ""
    DB_NAME: str = "postgres"
    DB_PORT: int = 5432

    class Config:
        env_file = ".env"

settings = Settings()
