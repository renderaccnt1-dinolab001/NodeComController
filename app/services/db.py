from sqlmodel import create_engine, Session
from sqlalchemy.engine import URL
import json
from app.services.kv_storage import StorageService
from app.core.config import settings


def get_engine():
    """
    Build a SQLAlchemy engine using Supabase credentials.

    Resolution order:
      1. KV storage key "supabase_creds"  ← populated by lifespan fetch from Primary Backend
      2. settings.DB_* env vars            ← fallback for local dev / if Primary Backend is down
    """
    creds = {}

    # Priority 1: credentials fetched from Primary Backend and cached in KV
    try:
        creds_json = StorageService.get_data("supabase_creds")
        if creds_json:
            creds = json.loads(creds_json)
    except Exception:
        pass

    # Priority 2: fall back to env vars in settings
    if not creds.get("db_host") or not creds.get("db_password"):
        creds = {
            "db_user":     settings.DB_USER,
            "db_password": settings.DB_PASSWORD,
            "db_host":     settings.DB_HOST,
            "db_name":     settings.DB_NAME,
            "db_port":     settings.DB_PORT,
        }

    if not creds.get("db_host") or not creds.get("db_password"):
        raise RuntimeError(
            "Supabase credentials are not available. "
            "Either the Primary Backend fetch failed or DB_HOST / DB_PASSWORD "
            "env vars are not set. Check controller startup logs."
        )

    db_url = URL.create(
        drivername="postgresql+psycopg2",
        username=creds.get("db_user", "postgres"),
        password=creds.get("db_password"),
        host=creds.get("db_host"),
        port=int(creds.get("db_port", 5432)),
        database=creds.get("db_name", "postgres"),
    )
    return create_engine(str(db_url))


def get_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session
