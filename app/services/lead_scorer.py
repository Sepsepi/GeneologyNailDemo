"""Lead scoring service for citizenship eligibility"""
from sqlalchemy.orm import Session
from app.models import Person, Relationship, Address
from typing import Optional, Dict, List


class LeadScorer:
    """Calculate lead quality scores for German citizenship eligibility"""

    @staticmethod
    def calculate_lead_score(person: Person, db: Session) -> int:
        """
        Calculate lead score (0-100) based on:
        - Has German-born ancestor (25 pts)
        - Multiple source verification (20 pts)
        - Complete family tree (15 pts)
        - Recent address available (15 pts)
        - Multiple addresses (10 pts)
        - Living descendant (10 pts)
        - Complete dates (5 pts)
        """
        score = 0

        # Check if has German-born ancestor
        if LeadScorer.has_german_ancestor(person, db):
            score += 25

        # Count sources
        raw_records_count = len(person.raw_records) if person.raw_records else 0
        if raw_records_count >= 3:
            score += 20
        elif raw_records_count == 2:
            score += 10

        # Check family tree completeness
        relationships = db.query(Relationship).filter(
            (Relationship.person_id == person.id) | (Relationship.related_person_id == person.id)
        ).all()

        if len(relationships) >= 3:
            score += 15
        elif len(relationships) >= 1:
            score += 7

        # Check for addresses
        if person.addresses:
            score += 15

            if len(person.addresses) > 1:
                score += 10

        # Living descendant (no death date)
        if not person.death_date:
            score += 10

        # Complete dates
        if person.birth_date:
            score += 5

        return min(score, 100)

    @staticmethod
    def has_german_ancestor(person: Person, db: Session, max_depth: int = 3) -> bool:
        """Check if person or ancestors were born in Germany"""
        # Direct check
        if person.birth_country and "Germany" in person.birth_country:
            return True

        # Check parents (simplified - would need recursive search in production)
        parent_rels = db.query(Relationship).filter(
            Relationship.person_id == person.id,
            Relationship.relationship_type == "parent"
        ).all()

        for rel in parent_rels:
            parent = db.query(Person).filter(Person.id == rel.related_person_id).first()
            if parent and parent.birth_country and "Germany" in parent.birth_country:
                return True

        return False

    @staticmethod
    def find_german_ancestor(person: Person, db: Session) -> Optional[Person]:
        """Find the German-born ancestor for this person"""
        # Check self first
        if person.birth_country and "Germany" in person.birth_country:
            return person

        # Check parents
        parent_rels = db.query(Relationship).filter(
            Relationship.person_id == person.id,
            Relationship.relationship_type == "parent"
        ).all()

        for rel in parent_rels:
            parent = db.query(Person).filter(Person.id == rel.related_person_id).first()
            if parent and parent.birth_country and "Germany" in parent.birth_country:
                return parent

        # Check grandparents (simplified)
        for rel in parent_rels:
            parent = db.query(Person).filter(Person.id == rel.related_person_id).first()
            if parent:
                grandparent_rels = db.query(Relationship).filter(
                    Relationship.person_id == parent.id,
                    Relationship.relationship_type == "parent"
                ).all()

                for gp_rel in grandparent_rels:
                    grandparent = db.query(Person).filter(Person.id == gp_rel.related_person_id).first()
                    if grandparent and grandparent.birth_country and "Germany" in grandparent.birth_country:
                        return grandparent

        return None

    @staticmethod
    def get_data_confidence(score: int, sources_count: int) -> str:
        """Determine data confidence level"""
        if score >= 80 and sources_count >= 3:
            return "high"
        elif score >= 60 and sources_count >= 2:
            return "medium"
        else:
            return "low"
