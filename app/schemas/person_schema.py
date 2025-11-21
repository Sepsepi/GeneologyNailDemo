from pydantic import BaseModel
from datetime import date
from typing import Optional


class PersonCreate(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    birth_date: Optional[date] = None
    birth_place: Optional[str] = None
    birth_city: Optional[str] = None
    birth_state: Optional[str] = None
    birth_country: Optional[str] = None
    death_date: Optional[date] = None
    death_place: Optional[str] = None
    sex: Optional[str] = None


class PersonResponse(BaseModel):
    id: int
    first_name: str
    middle_name: Optional[str]
    last_name: str
    birth_date: Optional[date]
    birth_place: Optional[str]
    birth_country: Optional[str]
    death_date: Optional[date]
    sex: Optional[str]
    confidence_score: float

    class Config:
        from_attributes = True
