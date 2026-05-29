from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any


def _sanitize_str(v: Any, max_len: int = 200) -> Optional[str]:
    if v is None:
        return None
    s = str(v).replace("\x00", "").strip()
    return s[:max_len] if s else None


class TicketPayload(BaseModel):
    ticket_id: str = Field(..., max_length=100, example="A1-0245")
    name: str = Field(..., max_length=200, example="Fazli")
    company: Optional[str] = Field(default=None, max_length=200, example="Fazli Corp.")
    title: Optional[str] = Field(default=None, max_length=200, example="CEO")
    ticket_type: str = Field(..., max_length=100, example="Delegate")

    @field_validator("ticket_id", "name", "ticket_type", mode="before")
    @classmethod
    def sanitize_str(cls, v: Any) -> str:
        result = _sanitize_str(v)
        if not result:
            raise ValueError("Field must be a non-empty string.")
        return result

    @field_validator("company", "title", mode="before")
    @classmethod
    def sanitize_optional_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, dict):
            for k in ("organisation_institution", "name", "company", "label"):
                val = v.get(k)
                if isinstance(val, str) and val.strip():
                    return _sanitize_str(val)
            return None
        return _sanitize_str(v)
