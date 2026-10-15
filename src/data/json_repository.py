"""Small JSON store with atomic replacement for each collection."""

import json
import os
import tempfile
import threading
from pathlib import Path


COLLECTIONS = {"users", "profiles", "inventory", "hampers", "donations", "access_log"}


class JsonRepository:
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
        with self.lock:
            value = self.read(collection)
            result = change(value)
            self.write(collection, value)
            return result
