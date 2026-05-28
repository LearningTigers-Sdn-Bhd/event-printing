from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any

class TicketPayload(BaseModel):
    ticket_id: str = Field(..., example="A1-0245")
    name: str = Field(..., example="Fazli")
    company: Optional[str] = Field(default=None, example="Fazli Corp.")
    title: Optional[str] = Field(default=None, example="CEO")
    ticket_type: str = Field(..., example="Delegate")

    @field_validator("company", mode="before")
    @classmethod
    def coerce_company(cls, v: Any):
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, dict):
            for k in ("organisation_institution", "name", "company", "label"):
                val = v.get(k)
                if isinstance(val, str) and val.strip():
                    return val
            return None
        return str(v)
