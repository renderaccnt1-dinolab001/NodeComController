import os
import tempfile
import threading
import importlib
from collections import defaultdict
from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, Session, create_engine
from app.core.drive_auth import get_authenticated_drive
from app.services.drivefs import GoogleDriveFS

_TMP = tempfile.gettempdir()

# ── Configuration Map ──────────────────────────────────────────────────────────
DB_CONFIGS = {
    "controller_data": {
        "drive_path": "/NodeCom/database/controller_data.db",
        "local_path": os.path.join(_TMP, "temp_controller_data.db"),
        "models": ["app.models"]  # Module containing the Controller models
    }
}

# ── Module-level state (keyed by db_type) ──────────────────────────────────────
_fs_instance: GoogleDriveFS | None = None
_engines = {}
_last_sync_modified_dates = {}
_upload_locks = defaultdict(threading.Lock)


def get_fs() -> GoogleDriveFS:
    global _fs_instance
    if _fs_instance is None:
        drive = get_authenticated_drive()
        _fs_instance = GoogleDriveFS(drive)
    return _fs_instance


def _get_engine(db_type: str):
    """Returns (or lazily creates) the SQLAlchemy engine for the specific DB."""
    if db_type not in _engines:
        local_path = DB_CONFIGS[db_type]["local_path"]
        sqlite_url = f"sqlite:///{local_path}"
        _engines[db_type] = create_engine(sqlite_url, echo=False, poolclass=NullPool)
    return _engines[db_type]


def _ensure_tables(db_type: str):
    """Dynamically imports the models for the requested DB and creates tables."""
    config = DB_CONFIGS[db_type]
    for module_path in config["models"]:
        importlib.import_module(module_path)
    
    SQLModel.metadata.create_all(_get_engine(db_type))


def _sync_down(fs: GoogleDriveFS, db_type: str):
    """Downloads the specific DB from Drive to the local cache."""
    drive_path = DB_CONFIGS[db_type]["drive_path"]
    local_path = DB_CONFIGS[db_type]["local_path"]
    
    if fs.exists(drive_path):
        print(f"[{db_type}] Database found in cloud storage. Syncing downward...")
        fs.read_file(drive_path, local_path)
    else:
        print(f"[{db_type}] No remote database found. Initializing blank local file...")
        open(local_path, 'w').close()
        
    _last_sync_modified_dates[db_type] = fs.get_modified_date(drive_path)


def _is_cache_fresh(fs: GoogleDriveFS, db_type: str) -> bool:
    """Returns True if the local DB matches the current Drive version."""
    drive_path = DB_CONFIGS[db_type]["drive_path"]
    local_path = DB_CONFIGS[db_type]["local_path"]
    last_sync = _last_sync_modified_dates.get(db_type)
    
    if last_sync is None or not os.path.exists(local_path):
        return False
    try:
        remote_date = fs.get_modified_date(drive_path)
        return remote_date is not None and remote_date == last_sync
    except Exception:
        return False


@contextmanager
def drive_db_session(db_type: str = "controller_data"):
    """
    Context manager for Drive-backed SQLite access.
    Accepts `db_type` ('app_data' or 'credentials') to isolate databases.
    """
    if db_type not in DB_CONFIGS:
        raise ValueError(f"Unknown database type: {db_type}")

    fs = get_fs()
    session_dirty = False
    drive_path = DB_CONFIGS[db_type]["drive_path"]
    local_path = DB_CONFIGS[db_type]["local_path"]

    # ── Phase 1: ensure local DB is current ───────────────────────────────────
    if _is_cache_fresh(fs, db_type):
        print(f"[{db_type}] Local cache is fresh.")
    else:
        with fs.lock(drive_path, timeout=45, max_age=120):
            if not _is_cache_fresh(fs, db_type):
                _sync_down(fs, db_type)

    # ── Phase 2: yield a SQLModel session backed by the local file ─────────────
    _ensure_tables(db_type)
    with Session(_get_engine(db_type)) as session:
        @event.listens_for(session, 'after_flush')
        def _on_flush(sess, ctx):
            nonlocal session_dirty
            session_dirty = True

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    # ── Phase 3: upload back to Drive only when data actually changed ──────────
    if session_dirty:
        with _upload_locks[db_type]:
            with fs.lock(drive_path, timeout=45, max_age=120):
                print(f"[{db_type}] Uploading updated database to cloud...")
                fs.write_file(drive_path, local_path)
                _last_sync_modified_dates[db_type] = fs.get_modified_date(drive_path)
                print(f"[{db_type}] Cloud sync complete.")
