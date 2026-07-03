import time
from contextlib import contextmanager
from sqlmodel import Session, create_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.services.drive_db import drive_db_session

_pg_engine = None
_supabase_down_until = 0

def _get_pg_engine():
    global _pg_engine
    if _pg_engine is None:
        # Fast timeout (2 seconds) so requests don't hang forever
        _pg_engine = create_engine(
            settings.db_url, 
            pool_pre_ping=True, 
            poolclass=NullPool,
            connect_args={"connect_timeout": 2}
        )
    return _pg_engine

def get_engine():
    return _get_pg_engine()

@contextmanager
def get_db_session():
    """
    Context manager that attempts to use the primary Supabase PostgreSQL DB.
    If Supabase is unreachable (or not configured), it falls back to the Drive-backed SQLite DB.
    """
    global _supabase_down_until
    use_fallback = False
    
    if settings.db_user:
        current_time = time.time()
        if current_time < _supabase_down_until:
            # Circuit breaker is active, don't even try connecting
            use_fallback = True
        else:
            try:
                # 1. Reload credentials from KV
                from app.services.kv_storage import StorageService
                global _pg_engine
                
                old_url = str(settings.db_url)
                for field in ("db_user", "db_password", "db_host", "db_name", "db_port"):
                    value = StorageService.get_data(field)
                    if value:
                        object.__setattr__(settings, field, int(value) if field == "db_port" else value)
                
                # 2. If credentials changed, force engine recreation and table initialization
                if str(settings.db_url) != old_url:
                    print("[DB] Supabase credentials updated from KV. Re-initializing engine.")
                    if _pg_engine is not None:
                        _pg_engine.dispose()
                        _pg_engine = None
                        
                    from sqlmodel import SQLModel
                    new_engine = _get_pg_engine()
                    try:
                        SQLModel.metadata.create_all(new_engine)
                        print("[DB] New Supabase tables verified.")
                    except Exception as meta_err:
                        print(f"[DB] Warning: failed to create tables on new database: {meta_err}")

                # 3. Test connection to Supabase before yielding the session
                with _get_pg_engine().connect() as conn:
                    pass
                _supabase_down_until = 0  # Reset on success
            except Exception as e:
                print(f"[DB] Supabase connection failed, falling back to Drive DB for next 60s.")
                _supabase_down_until = current_time + 60
                use_fallback = True
    else:
        use_fallback = True

    if use_fallback:
        with drive_db_session("controller_data") as session:
            yield session
    else:
        with Session(_get_pg_engine()) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

def get_session():
    """FastAPI Dependency wrapper for get_db_session"""
    with get_db_session() as session:
        yield session
