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
    db_user: str = "postgres"
    db_password: str = ""
    db_host: str = ""
    db_name: str = "postgres"
    db_port: int = 5432

    @property
    def db_url(self) -> str:
        from sqlalchemy.engine import URL
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
