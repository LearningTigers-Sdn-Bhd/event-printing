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

    def search_attendees(self, event_slug: str, method: str, value: str) -> list:
        """POST /v1/public/events/{slug}/check_in {method, value} -> matching guests.

        The same no-login search the EventzFlow check-in page uses (paid
        tickets, newest first, at most 10). Nothing is checked in here.
        """
        self._check_base()
        if not event_slug:
            raise BackendError("Event slug is not configured.")
        url = f"{self.base_url}/v1/public/events/{quote(event_slug, safe='')}/check_in"
        try:
            r = httpx.post(url, json={"method": method, "value": value}, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e
        body = _json_or_none(r)
        message = str(body.get("message") or "") if isinstance(body, dict) else ""
        if r.status_code == 404:
            if "event" in message.lower():
                raise BackendError("Event not found. Check the event name (slug).")
            return []  # "No attendees found"
        if r.status_code >= 400:
            raise BackendError(f"Search failed ({r.status_code}): {message or _safe_excerpt(r.text)}")
        data = body.get("data") if isinstance(body, dict) else None
        rows = data.get("attendees") if isinstance(data, dict) else None
        return [a for a in rows if isinstance(a, dict) and a.get("public_id")] if isinstance(rows, list) else []

    def fetch_ticket_groups(self, event_slug: str) -> Dict[str, Any]:
        """-> {"enabled": bool, "groups": [names]} for the event's ticket groups.

        The group list is staff-only (needs the API key and the numeric event
        id, which the public check-in info gives us). Events without groups
        answer 403 "not enabled", which is a normal "no groups", not an error.
        """
        self._check_base()
        if not event_slug:
            raise BackendError("Event slug is not configured.")
        if not self.api_key:
            raise BackendError("API key is not configured.")
        slug = quote(event_slug, safe="")
        try:
            info = httpx.get(f"{self.base_url}/v1/public/events/{slug}/check_in", timeout=self.timeout)
            body = _json_or_none(info)
            event_id = (body.get("data") or {}).get("id") if isinstance(body, dict) else None
            if info.status_code >= 400 or not event_id:
                raise BackendError("Event not found. Check the event name (slug).")
            r = httpx.get(f"{self.base_url}/v1/events/{quote(str(event_id), safe='')}/ticket_groups",
                          headers=self._auth_headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise BackendError(f"Network error contacting backend: {e}") from e
        body = _json_or_none(r)
        if r.status_code == 403 and "not enabled" in str((body or {}).get("error", "")).lower():
            return {"enabled": False, "groups": []}
        if r.status_code in (401, 403):
            raise BackendError("Not authorized to read ticket groups. Check your API key.")
        if r.status_code >= 400:
            raise BackendError(f"Group lookup failed ({r.status_code}): {_safe_excerpt(r.text)}")
        rows = body.get("groups") if isinstance(body, dict) else None
        names = []
        for g in rows if isinstance(rows, list) else []:
            name = str(g.get("name") or "").strip() if isinstance(g, dict) else ""
            if name and name not in names:
                names.append(name)
        return {"enabled": True, "groups": names}

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


def _json_or_none(r) -> Any:
    try:
        return r.json()
    except ValueError:
        return None


def _safe_excerpt(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")
