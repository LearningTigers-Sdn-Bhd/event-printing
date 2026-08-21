from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from typing import Optional, Any


def _sanitize_str(v: Any, max_len: int = 200) -> Optional[str]:
    if v is None:
        return None
    s = str(v).replace("\x00", "").strip()
    return s[:max_len] if s else None


class TicketPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str = Field(..., max_length=100, example="A1-0245")
    name: str = Field(..., max_length=200, example="Fazli")
    company: Optional[str] = Field(default=None, max_length=200, example="Fazli Corp.")
    title: Optional[str] = Field(default=None, max_length=200, example="CEO")
    ticket_type: str = Field(..., max_length=100, example="Delegate")
    country: Optional[str] = Field(default=None, max_length=100, example="Malaysia")
    table_no: Optional[str] = Field(default=None, max_length=50, example="12")

    @model_validator(mode="before")
    @classmethod
    def map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if not data.get("company"):
                data["company"] = data.get("organisation") or data.get("organization")
            if not data.get("table_no"):
                data["table_no"] = data.get("table_number") or data.get("table")
        return data

    @field_validator("ticket_id", "name", "ticket_type", mode="before")
    @classmethod
    def sanitize_str(cls, v: Any) -> str:
        result = _sanitize_str(v)
        if not result:
            raise ValueError("Field must be a non-empty string.")
        return result

    @field_validator("company", "title", "country", "table_no", mode="before")
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
