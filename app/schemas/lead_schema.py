from pydantic import BaseModel
from datetime import date
from typing import Optional


class GermanAncestor(BaseModel):
    name: str
    birth_place: str
    birth_date: Optional[date]
    naturalization_date: Optional[date]
    citizenship_eligible: bool


class LeadResponse(BaseModel):
    person_id: int
    name: str
    last_known_address: str
    german_ancestor: GermanAncestor
    lead_score: int
    data_confidence: str
    sources_count: int

    class Config:
        from_attributes = True
