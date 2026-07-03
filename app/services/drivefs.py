import os
import mimetypes
import time
import tempfile
import datetime
from pydrive2.drive import GoogleDrive

class GoogleDriveFS:
    # Comprehensive mapping of common extensions to their official MIME types
    COMMON_MIME_TYPES = {
        # Images
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
        
        # Documents & Text
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.html': 'text/html',
        '.css': 'text/css',
        
        # Archives
        '.zip': 'application/zip',
        '.rar': 'application/vnd.rar',
        '.7z': 'application/x-7z-compressed',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
        
        # Audio & Video
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        
        # Microsoft Office (Standard Binaries)
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }

    def __init__(self, drive_client: GoogleDrive):
        """Initializes the wrapper with an authenticated PyDrive2 client."""
        self.drive = drive_client
        # path → file_id cache. Avoids repeated ListFile traversals for the
        # same path segments across multiple operations in the same process.
        self._id_cache: dict = {}

    def _get_mime_type(self, filename: str) -> str:
        """Helper to determine MIME type from filename extension."""
        _, ext = os.path.splitext(filename.lower())
        
        # 1. Check our hardcoded common types first
        if ext in self.COMMON_MIME_TYPES:
            return self.COMMON_MIME_TYPES[ext]
        
        # 2. Fallback to Python's built-in system registry guess
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            return guessed_type
            
        # 3. Ultimate fallback if completely unknown
        return 'application/octet-stream'

    def _resolve_path(self, path: str, create_missing_folders: bool = False) -> tuple:
        """Internal helper to traverse a path string and return (item_id, item_metadata).

        Uses _id_cache to skip ListFile API calls for already-seen path segments.
        A FetchMetadata call on the cached ID replaces up to N ListFile calls,
        where N is the number of path segments.
        """
        parts = [p for p in path.strip('/').split('/') if p]
        current_id = 'root'
        current_item = None

        if not parts:
            return 'root', {'mimeType': 'application/vnd.google-apps.folder', 'title': 'root'}

        # Fast path: full path is already cached and we're not creating new folders.
        if not create_missing_folders:
            full_key = '/'.join(parts)
            if full_key in self._id_cache:
                drive_file = self.drive.CreateFile({'id': self._id_cache[full_key]})
                drive_file.FetchMetadata()
                return self._id_cache[full_key], drive_file

        for i, part in enumerate(parts):
            seg_key = '/'.join(parts[:i + 1])

            # Use cached ID for this segment if available.
            if not create_missing_folders and seg_key in self._id_cache:
                current_id = self._id_cache[seg_key]
                if i == len(parts) - 1:
                    # Final segment: fetch current metadata via direct ID lookup.
                    drive_file = self.drive.CreateFile({'id': current_id})
                    drive_file.FetchMetadata()
                    current_item = drive_file
                continue

            query = f"title = '{part}' and '{current_id}' in parents and trashed = false"
            file_list = self.drive.ListFile({'q': query}).GetList()

            if file_list:
                current_item = file_list[0]
                current_id = current_item['id']
                # Cache each segment we resolve so future traversals skip it.
                self._id_cache[seg_key] = current_id
            else:
                if create_missing_folders and i < len(parts) - 1:
                    current_id = self._mkdir_by_id(part, current_id)
                    self._id_cache[seg_key] = current_id
                    continue
                if i == len(parts) - 1:
                    return current_id, part
                raise FileNotFoundError(f"Path component '{part}' does not exist.")

        return current_id, current_item

    def _mkdir_by_id(self, folder_name: str, parent_id: str) -> str:
        """Helper to create a single folder under a specific parent ID."""
        folder = self.drive.CreateFile({
            'title': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [{'id': parent_id}]
        })
        folder.Upload()
        return folder['id']

    def exists(self, path: str) -> bool:
        """Returns True if the path exists, False otherwise."""
        try:
            _, item = self._resolve_path(path)
            return not isinstance(item, str)
        except FileNotFoundError:
            return False

    def mkdir(self, path: str):
        """Creates a directory path (handles nested parents)."""
        self._resolve_path(path, create_missing_folders=True)

    def ls(self, path: str = "/") -> list:
        """Lists contents of a directory path."""
        item_id, item = self._resolve_path(path)
        if item['mimeType'] != 'application/vnd.google-apps.folder':
            raise NotADirectoryError(f"'{path}' is a file, not a directory.")

        query = f"'{item_id}' in parents and trashed = false"
        file_list = self.drive.ListFile({'q': query}).GetList()
        
        results = []
        for f in file_list:
            is_dir = f['mimeType'] == 'application/vnd.google-apps.folder'
            results.append(f"{f['title']}/" if is_dir else f['title'])
        return results

    def write_file(self, target_path: str, local_source_path: str, explicit_mime: str = ""):
        """
        Uploads or overwrites a file. Automatically resolves and assigns the MIME type.
        You can pass explicit_mime="type/string" to manually override auto-detection.
        """
        resolved = self._resolve_path(target_path, create_missing_folders=True)
        
        # Determine correct MIME type
        filename = os.path.basename(target_path)
        mime_type = explicit_mime if explicit_mime!="" else self._get_mime_type(filename)
        
        if isinstance(resolved, tuple) and isinstance(resolved[1], str):
            # File is brand new: resolved is (parent_id, filename)
            parent_id, filename = resolved
            metadata = {
                'title': filename,
                'mimeType': mime_type,
                'parents': [{'id': parent_id}]
            }
            drive_file = self.drive.CreateFile(metadata)
            print(f"Creating new file with MIME type [{mime_type}]")
        else:
            # File already exists: resolved is (file_id, file_metadata)
            file_id, _ = resolved
            metadata = {
                'id': file_id,
                'mimeType': mime_type # Keep type updated on overwrite
            }
            drive_file = self.drive.CreateFile(metadata)
            print(f"Updating existing file with MIME type [{mime_type}]")

        # Load content and sync to cloud
        drive_file.SetContentFile(local_source_path)
        drive_file.Upload()

        # Keep the ID cache up-to-date with the confirmed file ID.
        cache_key = '/'.join([p for p in target_path.strip('/').split('/') if p])
        self._id_cache[cache_key] = drive_file['id']

    def read_file(self, drive_path: str, local_destination_path: str):
        """Downloads a file from the wrapper path to a local physical path."""
        file_id, item = self._resolve_path(drive_path)
        if isinstance(item, str):
            raise FileNotFoundError(f"File '{drive_path}' does not exist on Google Drive.")
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            raise IsADirectoryError(f"'{drive_path}' is a directory.")

        drive_file = self.drive.CreateFile({'id': file_id})
        drive_file.GetContentFile(local_destination_path)

    def rm(self, path: str, permanent: bool = False):
        """Removes a file or folder (trashes by default)."""
        item_id, item = self._resolve_path(path)
        if isinstance(item, str):
            raise FileNotFoundError(f"File '{path}' does not exist on Google Drive.")
        drive_file = self.drive.CreateFile({'id': item_id})
        if permanent:
            drive_file.Delete()
        else:
            drive_file.Trash()
        # Evict the removed path from the ID cache.
        cache_key = '/'.join([p for p in path.strip('/').split('/') if p])
        self._id_cache.pop(cache_key, None)
    
    def acquire_lock(self, target_path: str, timeout_seconds: int = 60, poll_interval: float = 2.0, max_lock_age_seconds: int = 300) -> bool:
        """
        Attempts to acquire a lock. If a stale lock is detected (older than max_lock_age_seconds),
        it will automatically break and heal the lock.
        """
        lock_path = target_path + ".lock"
        start_time = time.time()

        print(f"Attempting to acquire lock for {target_path}...")
        while True:
            try:
                # Check if the lock file exists and get its metadata
                lock_id, lock_item = self._resolve_path(lock_path)
                if isinstance(lock_item, str):
                    raise FileNotFoundError
                
                # STALE LOCK DETECTION LAYER
                created_time_str = lock_item.get('createdDate') # e.g., "2026-06-05T15:07:51.123Z"
                if created_time_str:
                    # Parse Google's UTC timestamp (handling the 'Z' safely)
                    lock_time = datetime.datetime.fromisoformat(created_time_str.replace('Z', '+00:00'))
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    age_seconds = (now_utc - lock_time).total_seconds()
                    
                    if age_seconds > max_lock_age_seconds:
                        print(f"--> [⚠️ STALE LOCK] Found dead lock from a crashed instance (Age: {int(age_seconds)}s).")
                        print("--> Breaking stale lock and self-healing...")
                        self.release_lock(target_path)
                        continue # Re-loop immediately to capture the newly freed spot
                
            except FileNotFoundError:
                # EXCELLENT: No lock file exists. Let's create one.
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_f:
                    temp_f.write(f"Locked by active instance at {time.time()}")
                    temp_path = temp_f.name

                try:
                    self.write_file(lock_path, temp_path, explicit_mime="text/plain")
                    print("--> Lock acquired successfully!")
                    return True
                except Exception as e:
                    print(f"Collision detected while creating lock: {e}. Retrying...")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            
            # Check if this current process has been waiting too long to get a normal active lock
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Could not acquire lock for {target_path}. Operation timed out.")
            
            print(f"Active lock file exists. Retrying in {poll_interval} seconds...")
            time.sleep(poll_interval)

    def release_lock(self, target_path: str):
        """Removes the .lock file from Google Drive."""
        lock_path = target_path + ".lock"
        try:
            # Bypass cache and check if it's there
            item_id, _ = self._resolve_path(lock_path)
            # Use permanent=True so we don't clutter the Google Drive Trash bin
            self.rm(lock_path, permanent=True)
            print("--> Lock released.")
        except FileNotFoundError:
            # Lock was already deleted or broken by another self-healing instance
            pass

    def get_modified_date(self, path: str) -> str | None:
        """Returns the Drive modifiedDate for a file at the given path.

        Uses the cached file ID (when available) to make a single direct
        FetchMetadata call instead of N ListFile traversals.
        Returns None if the file does not exist or on any error.
        """
        try:
            file_id, item = self._resolve_path(path)
            if isinstance(item, str):
                return None
            return item.get('modifiedDate')
        except FileNotFoundError:
            return None

    class _LockContext:
        """Internal helper for Python's 'with' statement context manager."""
        def __init__(self, fs_instance, target_path, timeout, max_age):
            self.fs = fs_instance
            self.target_path = target_path
            self.timeout = timeout
            self.max_age = max_age

        def __enter__(self):
            self.fs.acquire_lock(
                self.target_path, 
                timeout_seconds=self.timeout, 
                max_lock_age_seconds=self.max_age
            )
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.fs.release_lock(self.target_path)

    def lock(self, target_path: str, timeout: int = 60, max_age: int = 300):
        """
        Exposes the lock context manager interface.
        max_age: Force-delete locks older than this many seconds (default: 5 minutes).
        """
        return self._LockContext(self, target_path, timeout, max_age)