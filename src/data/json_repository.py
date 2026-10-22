"""Small JSON store with atomic replacement for each collection."""

import json
import os
import tempfile
import threading
from pathlib import Path


COLLECTIONS = {"users", "profiles", "inventory", "hampers", "donations", "access_log"}


class JsonRepository:
    """File-backed store: one JSON file per collection inside data_dir.

    Folder resolution order: the data_dir argument (used by tests with temporary
    folders), then the FOODSHARE_DATA_DIR environment variable, then the project's
    own data/ folder.
    """

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or os.environ.get("FOODSHARE_DATA_DIR") or
                             Path(__file__).resolve().parents[2] / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, collection):
        if collection not in COLLECTIONS:
            raise ValueError("Unknown data collection")
        return self.data_dir / f"{collection}.json"

    def read(self, collection):
        """Return the collection: a list, or a dict for "donations". Missing or empty files give an empty value."""
        with self.lock:
            path = self._path(collection)
            if not path.exists() or not path.read_text(encoding="utf-8").strip():
                return {} if collection == "donations" else []
            return json.loads(path.read_text(encoding="utf-8"))

    def write(self, collection, value):
        with self.lock:
            path = self._path(collection)
            handle, temporary = tempfile.mkstemp(prefix=f".{collection}-", suffix=".tmp", dir=self.data_dir)
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def update(self, collection, change):
        """Read, modify and save a collection as one step while holding the lock.

        `change` receives the loaded value and must MODIFY IT IN PLACE (append, set keys,
        replace a slice). Its return value is handed back to the caller, but a new object
        it builds is NOT saved. The file is rewritten even if nothing changed, and if
        `change` raises, nothing is written, so validation errors never leave half-saved data.
        """
        with self.lock:
            value = self.read(collection)
            result = change(value)
            self.write(collection, value)
            return result
