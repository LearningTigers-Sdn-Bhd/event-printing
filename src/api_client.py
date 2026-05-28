"""HTTP client for the EventzFlow backend (ticket lookup + check-in)."""
from typing import Any, Dict, Optional

import httpx


class BackendClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_key = api_key.strip() if api_key else ""
        self.timeout = timeout

    def _check_base(self):
        if not self.base_url:
            raise BackendError("Backend URL is not configured.")

    def _auth_headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        # The Rails backend accepts a raw API key in the Authorization header
        # (no "Bearer " prefix), see Authenticable concern.
        return {"Authorization": self.api_key}

    def fetch_ticket(self, event_slug: str, public_id: str) -> Dict[str, Any]:
        """GET /v1/public/events/{event_slug}/tickets/{public_id}"""
        self._check_base()
        if not event_slug:
            raise BackendError("Event slug is not configured.")
        url = f"{self.base_url}/v1/public/events/{event_slug}/tickets/{public_id}"
        try:
            r = httpx.get(url, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e

        if r.status_code == 404:
            raise BackendError("Ticket not found for this event.")
        if r.status_code >= 400:
            raise BackendError(f"Lookup failed ({r.status_code}): {_safe_excerpt(r.text)}")

        try:
            payload = r.json()
        except ValueError as e:
            raise BackendError("Lookup returned non-JSON response.") from e

        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise BackendError("Lookup response missing data field.")
        return data

    def check_in(self, public_id: str) -> Dict[str, Any]:
        """PATCH /v1/scan/{public_id}/check_in (requires api key)."""
        self._check_base()
        if not self.api_key:
            raise BackendError("API key is not configured. Cannot mark ticket as scanned.")
        url = f"{self.base_url}/v1/scan/{public_id}/check_in"
        try:
            r = httpx.patch(url, headers=self._auth_headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e

        # Already-checked-in returns 422 with informative body — surface as a soft error.
        if r.status_code == 422:
            try:
                body = r.json()
                msg = body.get("error") or body.get("message") or "Ticket already checked in."
            except ValueError:
                msg = "Ticket already checked in."
            raise BackendAlreadyCheckedIn(msg)
        if r.status_code in (401, 403):
            raise BackendError("Not authorized. Check your API key permissions.")
        if r.status_code == 404:
            raise BackendError("Ticket not found while attempting check-in.")
        if r.status_code >= 400:
            raise BackendError(f"Check-in failed ({r.status_code}): {_safe_excerpt(r.text)}")

        try:
            return r.json() or {}
        except ValueError:
            return {}


class BackendError(RuntimeError):
    pass


class BackendAlreadyCheckedIn(BackendError):
    pass


def _safe_excerpt(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")
