from pydantic import BaseModel
from typing import List, Dict, Any

class TicketItem(BaseModel):
    appointment_ref: str
    ticket: Dict[str, Any]

# O schema do response será uma lista de TicketItem

class CheckinResponse(BaseModel):
    success: bool = True
    message: str