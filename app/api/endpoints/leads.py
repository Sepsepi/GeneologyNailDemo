"""Leads endpoint for retrieving potential citizenship leads"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Person, Address, Relationship
from app.schemas import LeadResponse, GermanAncestor
from app.services.lead_scorer import LeadScorer
from typing import List

router = APIRouter()


@router.get("/leads", response_model=List[LeadResponse])
def get_leads(
    min_score: int = Query(default=70, ge=0, le=100),
    has_german_ancestor: bool = Query(default=True),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db)
):
    """
    Get potential citizenship leads
    Returns persons with German ancestors and their details
    """
    leads = []

    # Get all persons (in production, would use better filtering)
    persons = db.query(Person).all()

    for person in persons:
        # Calculate lead score
        score = LeadScorer.calculate_lead_score(person, db)

        if score < min_score:
            continue

        # Check for German ancestor
        german_ancestor = LeadScorer.find_german_ancestor(person, db)

        if has_german_ancestor and not german_ancestor:
            continue

        if not german_ancestor:
            continue  # Skip if no German ancestor found

        # Get last known address
        last_address = db.query(Address).filter(
            Address.person_id == person.id
        ).order_by(desc(Address.from_date)).first()

        if last_address:
            # Build address string, skipping None values
            parts = []
            if last_address.street:
                parts.append(last_address.street)
            if last_address.city:
                parts.append(last_address.city)
            if last_address.state:
                parts.append(last_address.state)
            if last_address.postal_code:
                parts.append(last_address.postal_code)
            address_str = ", ".join(parts) if parts else "Address unknown"
        else:
            address_str = "Address unknown"

        # Build response
        sources_count = len(person.raw_records) if person.raw_records else 0
        confidence = LeadScorer.get_data_confidence(score, sources_count)

        # Get naturalization date from raw records if available
        nat_date = None
        if person.raw_records:
            for raw in person.raw_records:
                if raw.normalized_data.get("naturalization_date"):
                    nat_date = raw.normalized_data["naturalization_date"]
                    break

        lead = LeadResponse(
            person_id=person.id,
            name=f"{person.first_name} {person.middle_name or ''} {person.last_name}".strip(),
            last_known_address=address_str,
            german_ancestor=GermanAncestor(
                name=f"{german_ancestor.first_name} {german_ancestor.last_name}",
                birth_place=german_ancestor.birth_place or "Germany",
                birth_date=german_ancestor.birth_date,
                naturalization_date=nat_date,
                citizenship_eligible=True  # Simplified - would have complex logic
            ),
            lead_score=score,
            data_confidence=confidence,
            sources_count=sources_count
        )

        leads.append(lead)

    # Sort by score descending
    leads.sort(key=lambda x: x.lead_score, reverse=True)

    return leads[:limit]


@router.get("/leads/{person_id}", response_model=LeadResponse)
def get_lead_by_id(person_id: int, db: Session = Depends(get_db)):
    """Get a specific lead by person ID"""
    person = db.query(Person).filter(Person.id == person_id).first()

    if not person:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person not found")

    score = LeadScorer.calculate_lead_score(person, db)
    german_ancestor = LeadScorer.find_german_ancestor(person, db)

    if not german_ancestor:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No German ancestor found for this person")

    last_address = db.query(Address).filter(
        Address.person_id == person.id
    ).order_by(desc(Address.from_date)).first()

    if last_address:
        # Build address string, skipping None values
        parts = []
        if last_address.street:
            parts.append(last_address.street)
        if last_address.city:
            parts.append(last_address.city)
        if last_address.state:
            parts.append(last_address.state)
        if last_address.postal_code:
            parts.append(last_address.postal_code)
        address_str = ", ".join(parts) if parts else "Address unknown"
    else:
        address_str = "Address unknown"

    sources_count = len(person.raw_records) if person.raw_records else 0
    confidence = LeadScorer.get_data_confidence(score, sources_count)

    nat_date = None
    if person.raw_records:
        for raw in person.raw_records:
            if raw.normalized_data.get("naturalization_date"):
                nat_date = raw.normalized_data["naturalization_date"]
                break

    return LeadResponse(
        person_id=person.id,
        name=f"{person.first_name} {person.middle_name or ''} {person.last_name}".strip(),
        last_known_address=address_str,
        german_ancestor=GermanAncestor(
            name=f"{german_ancestor.first_name} {german_ancestor.last_name}",
            birth_place=german_ancestor.birth_place or "Germany",
            birth_date=german_ancestor.birth_date,
            naturalization_date=nat_date,
            citizenship_eligible=True
        ),
        lead_score=score,
        data_confidence=confidence,
        sources_count=sources_count
    )
