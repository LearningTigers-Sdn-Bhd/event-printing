from pydantic import BaseModel, Field
from typing import Optional

class TicketPayload(BaseModel):
    ticket_id: str = Field(..., example="A1-0245")
    name: str = Field(..., example="Fazli")
    company: Optional[str] = Field(default=None, example="Fazli Corp.")
    title: Optional[str] = Field(default=None, example="CEO")
    ticket_type: str = Field(..., example="Delegate")