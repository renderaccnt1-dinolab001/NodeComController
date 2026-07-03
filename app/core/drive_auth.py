import os
import json
import time
import tempfile
import urllib.parse
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from app.services.kv_storage import StorageService
class DriveAuthRequiredException(Exception):
    def __init__(self, message, creds_key):
        super().__init__(message)
        self.creds_key = creds_key

_TMP = tempfile.gettempdir()

def get_credentials_file_path(creds_key: str) -> str:
    return os.path.join(_TMP, f"temp_{creds_key}")

def get_authenticated_drive(creds_key: str = "mycreds.txt") -> GoogleDrive:
    """
    Authenticates and returns a GoogleDrive instance.
    Fetches credentials from Vercel KV.
    If credentials are invalid or expired, it pings Discord and raises an exception.
    """
    CREDENTIALS_FILE = get_credentials_file_path(creds_key)
    
    gauth = GoogleAuth()
    
    # 1. Fetch credentials from KV
    creds_content = None
    try:
        creds_content = StorageService.get_data(creds_key)
    except Exception:
        pass

    if creds_content:
        with open(CREDENTIALS_FILE, "w") as f:
            f.write(creds_content)
        gauth.LoadCredentialsFile(CREDENTIALS_FILE)

    # 2. Check credentials and Authenticate if needed
    if gauth.credentials is None:
        print(f"Alert: Google Drive Authentication missing for {creds_key}. Token not found.")
        raise DriveAuthRequiredException(f"Google Drive Authentication required for {creds_key}. Token not found.", creds_key)
    elif gauth.access_token_expired:
        try:
            gauth.Refresh()
            gauth.SaveCredentialsFile(CREDENTIALS_FILE)
            _upload_creds_to_kv(creds_key)
        except Exception as e:
            # Refresh failed, need re-auth
            print(f"Alert: Google Drive Token Refresh Failed for {creds_key}. Cause: {e}")
            raise DriveAuthRequiredException(f"Google Drive Authentication required for {creds_key}. Refresh failed.", creds_key)
    else:
        gauth.Authorize()

    # 3. Cleanup temp files
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)

    return GoogleDrive(gauth)

def _upload_creds_to_kv(creds_key: str):
    CREDENTIALS_FILE = get_credentials_file_path(creds_key)
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            creds_content = f.read()
            StorageService.save_data(creds_key, creds_content)
