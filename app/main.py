from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
from app.api.routes import router as api_router
from app.core.config import settings
from app.services.kv_storage import StorageService


def initialize_database():
    from app.core.config import settings
    from app.services.kv_storage import StorageService
    print("Loading Supabase credentials from KV...")
    for field in ("db_user", "db_password", "db_host", "db_name", "db_port"):
        value = StorageService.get_data(field)
        if value:
            object.__setattr__(settings, field, int(value) if field == "db_port" else value)
            
    print("Connecting to Supabase and ensuring tables exist...")
    try:
        if settings.db_user:
            from app.services.db_session import get_engine
            from sqlmodel import SQLModel
            import app.models  # registers all table classes
            pg_engine = get_engine()
            SQLModel.metadata.create_all(pg_engine)
            print("Supabase tables verified.")
            return True
        else:
            print("Warning: No Supabase credentials loaded. Operating in Drive-only mode.")
            return False
    except Exception as e:
        print(f"[Startup/Refresh] Postgres table creation skipped or failed. Falling back to Drive DB. ({e})")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="NodeCom Controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
