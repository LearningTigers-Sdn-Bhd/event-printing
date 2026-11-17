"""HTTP client for the EventzFlow backend (ticket lookup + check-in)."""
from typing import Any, Dict
from urllib.parse import quote

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
        return {"Authorization": self.api_key}

    def fetch_ticket(self, event_slug: str, public_id: str) -> Dict[str, Any]:
        """GET /v1/public/events/{event_slug}/tickets/{public_id}"""
        self._check_base()
        if not event_slug:
            raise BackendError("Event slug is not configured.")
        slug = quote(event_slug, safe="")
        pid = quote(public_id, safe="")
        url = f"{self.base_url}/v1/public/events/{slug}/tickets/{pid}"
        try:
            r = httpx.get(url, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e

        if r.status_code == 404:
            raise BackendError("Ticket not found for this event.")
        if r.status_code in (401, 403):
            raise BackendError("Not authorized. Check your API key.")
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

    def fetch_ticket_types(self, event_slug: str) -> list:
        """GET /v1/public/events/{event_slug}/ticket_types -> list of type names.

        Only the event's publicly listed types come back; hidden ones (staff,
        comps) have to be typed in by hand on the dashboard.
        """
        self._check_base()
        if not event_slug:
            raise BackendError("Event slug is not configured.")
        url = f"{self.base_url}/v1/public/events/{quote(event_slug, safe='')}/ticket_types"
        try:
            r = httpx.get(url, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e
        if r.status_code == 404:
            raise BackendError("Event not found. Check the event name (slug).")
        if r.status_code >= 400:
            raise BackendError(f"Ticket type lookup failed ({r.status_code}): {_safe_excerpt(r.text)}")
        try:
            data = r.json().get("data")
        except (ValueError, AttributeError) as e:
            raise BackendError("Ticket type lookup returned an unexpected response.") from e
        names = []
        for item in data if isinstance(data, list) else []:
            name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
            if name and name not in names:
                names.append(name)
        return names

    def check_in(self, public_id: str) -> Dict[str, Any]:
        """PATCH /v1/scan/{public_id}/check_in (requires api key)."""
        self._check_base()
        if not self.api_key:
            raise BackendError("API key is not configured. Cannot mark ticket as scanned.")
        pid = quote(public_id, safe="")
        url = f"{self.base_url}/v1/scan/{pid}/check_in"
        try:
            r = httpx.patch(url, headers=self._auth_headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e

        if r.status_code == 422:
            try:
                body = r.json()
            except ValueError:
                body = None
            if not isinstance(body, dict):
                raise BackendAlreadyCheckedIn("Ticket already checked in.")
            msg = body.get("error") or body.get("message") or "Ticket already checked in."
            # 422 is also how the backend refuses unpaid tickets. Only the
            # already-scanned refusal carries checked_in_at / blocked_by —
            # anything else must not be offered a reprint.
            if "checked_in_at" in body or "blocked_by" in body or "already" in str(msg).lower():
                raise BackendAlreadyCheckedIn(msg, body)
            raise BackendError(msg)
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
    """Carries who/when/where of the earlier scan when the backend reports it."""

    def __init__(self, message: str, body: Dict[str, Any] | None = None):
        super().__init__(message)
        blocked = (body or {}).get("blocked_by")
        blocked = blocked if isinstance(blocked, dict) else {}
        self.checked_in_at = (body or {}).get("checked_in_at") or blocked.get("scanned_at")
        self.checked_in_by = blocked.get("scanned_by_name")
        self.location = blocked.get("location_name")


def _safe_excerpt(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")
