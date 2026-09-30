"""JSON file-based state store adapter implementing StateStore port."""

import json
import threading
from pathlib import Path
from typing import Any, Optional

from obtainhub.ports import StateStore


class JsonStateStore(StateStore):
    """JSON file implementation of StateStore."""

    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure state file exists with valid JSON."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self.state_file.write_text("[]", encoding="utf-8")

    def _load_raw(self) -> list[dict]:
        """Load raw JSON data."""
        try:
            content = self.state_file.read_text(encoding="utf-8")
            if not content.strip():
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    def _save_raw(self, data: list[dict]) -> None:
        """Save raw JSON data atomically."""
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.replace(self.state_file)
        except OSError:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def load(self) -> list[dict]:
        with self._lock:
            return self._load_raw()

    def save(self, apps: list[dict]) -> None:
        with self._lock:
            self._save_raw(apps)

    def add_app(self, app: dict) -> None:
        with self._lock:
            apps = self._load_raw()
            apps.append(app)
            self._save_raw(apps)

    def update_app(self, app_id: str, updates: dict) -> None:
        with self._lock:
            apps = self._load_raw()
            for i, app in enumerate(apps):
                if app.get("id") == app_id:
                    apps[i] = {**app, **updates}
                    break
            else:
                return  # Not found
            self._save_raw(apps)

    def remove_app(self, app_id: str) -> None:
        with self._lock:
            apps = self._load_raw()
            apps = [a for a in apps if a.get("id") != app_id]
            self._save_raw(apps)

    def get_app(self, app_id: str) -> Optional[dict]:
        with self._lock:
            apps = self._load_raw()
            for app in apps:
                if app.get("id") == app_id:
                    return app
            return None

    def get_all_apps(self) -> list[dict]:
        with self._lock:
            return self._load_raw()

    def add_check_history(self, entry: dict) -> None:
        with self._lock:
            # Store check history in a separate file
            history_file = self.state_file.with_name("check_history.json")
            history = []
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    history = []
            history.append(entry)
            temp_file = history_file.with_suffix(".tmp")
            try:
                temp_file.write_text(json.dumps(history, indent=2), encoding="utf-8")
                temp_file.replace(history_file)
            except OSError:
                if temp_file.exists():
                    temp_file.unlink()

    def get_check_history(self) -> dict:
        with self._lock:
            history_file = self.state_file.with_name("check_history.json")
            if not history_file.exists():
                return {}
            try:
                history = json.loads(history_file.read_text(encoding="utf-8"))
                return {e.get("app_name", "").lower(): e for e in history}
            except (json.JSONDecodeError, OSError):
                return {}

    def clear_check_history(self) -> None:
        with self._lock:
            history_file = self.state_file.with_name("check_history.json")
            if history_file.exists():
                history_file.unlink()