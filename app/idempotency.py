from __future__ import annotations

import json
import os
from typing import Dict


class IdempotencyStore:
    def __init__(self, data_dir: str) -> None:
        self._path = os.path.join(data_dir, "idempotency.json")
        self._cache: Dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            self._cache = {}
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            self._cache = json.load(handle)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(self._cache, handle, ensure_ascii=True, indent=2)

    def is_processed(self, action_key: str) -> bool:
        return self._cache.get(action_key, False)

    def mark_processed(self, action_key: str) -> None:
        self._cache[action_key] = True
        self._save()
