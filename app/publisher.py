from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from app.utils import model_validate


class MaestroPublisher:
    def __init__(self, base_url: str, timeout_s: float = 8.0, retries: int = 2) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._retries = retries

    def publish_event(self, event_draft: Dict[str, Any], dma_rules: Any) -> Optional[Dict[str, Any]]:
        event_model = getattr(dma_rules, "EventDraft", None)
        if event_model is not None:
            model_validate(event_model, event_draft)
        else:
            required_fields = ("name", "source", "location_id", "payload")
            missing = [field for field in required_fields if field not in event_draft]
            if missing:
                raise ValueError(f"Invalid event_draft: missing fields {missing}")

        url = f"{self._base_url}/events/publish"
        last_error: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                response = requests.post(url, json=event_draft, timeout=self._timeout_s)
                response.raise_for_status()
                if response.content:
                    return response.json()
                return None
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self._retries:
                    break
                time.sleep(0.8 * (attempt + 1))
        if last_error:
            raise last_error
        return None
