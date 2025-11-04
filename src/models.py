from pydantic import BaseModel, Field
from typing import Optional

class TicketPayload(BaseModel):
    """
    Schema for the data required to generate and print a ticket.
    """
    ticket_id: str = Field(..., example="A1-0245")
    name: str = Field(..., example="Fazli")
    company: str = Field(..., example="Fazli Corp.")
    title: str = Field(..., example="CEO")
    ticket_type: Optional[str] = Field(default="Delegate")