from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
from app.api.routes import router as api_router
from app.core.config import settings
from app.services.kv_storage import StorageService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Step 1: Fetch Supabase credentials from the Primary Backend ───────────
    # The Primary Backend is the single source of truth for all secrets.
    # It verifies the request with the x-controller-api-key header.
    print("Fetching Supabase credentials from Primary Backend...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.PRIMARY_BACKEND_URL}/api/controllers/credentials/supabase",
                headers={"x-controller-api-key": settings.CONTROLLER_API_KEY},
                follow_redirects=True,
            )
            response.raise_for_status()
            creds = response.json()
            if not creds.get("db_host") or not creds.get("db_password"):
                raise ValueError(
                    "Primary Backend returned empty DB credentials. "
                    "Add db_host / db_password / db_user / db_name to the "
                    "Primary Backend's environment variables (Vercel dashboard)."
                )
            StorageService.save_data("supabase_creds", json.dumps(creds))
            print("Supabase credentials fetched and cached in KV.")
    except Exception as e:
        print(f"[Warning] Could not fetch Supabase credentials: {e}")

    # ── Step 2: Create all SQLModel tables (idempotent) ───────────────────────
    # Uses the credentials just stored in KV (or falls back to env vars).
    try:
        from sqlmodel import SQLModel
        import app.models  # noqa: F401 — registers all table classes
        from app.services.db import get_engine
        engine = get_engine()
        SQLModel.metadata.create_all(engine)
        print("Database tables verified / created.")
    except Exception as e:
        print(f"[Warning] Could not create/verify tables: {e}")

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
