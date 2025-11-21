"""Deduplication service for merging duplicate person records"""
from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
from app.models import Person, RawPersonRecord, MatchCandidate
from app.services.matcher import PersonMatcher


class Deduplicator:
    """Handles person deduplication and merging"""

    def __init__(self, db: Session):
        self.db = db
        self.matcher = PersonMatcher()

    def find_matches_for_record(self, record_data: Dict, existing_persons: List[Person]) -> List[Tuple[Person, float, Dict]]:
        """
        Find potential matches for a new record among existing persons
        Returns: List of (person, score, details) tuples
        """
        matches = []

        for person in existing_persons:
            person_dict = {
                "first_name": person.first_name,
                "middle_name": person.middle_name,
                "last_name": person.last_name,
                "birth_date": person.birth_date,
                "birth_place": person.birth_place,
                "birth_country": person.birth_country
            }

            is_match, score, details = self.matcher.is_match(record_data, person_dict)

            if is_match:
                matches.append((person, score, details))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def merge_person_data(self, existing: Person, new_data: Dict) -> Person:
        """
        Merge new data into existing person record
        Uses most complete/recent data
        """
        # Fill in missing fields from new data
        if not existing.middle_name and new_data.get("middle_name"):
            existing.middle_name = new_data["middle_name"]

        if not existing.birth_date and new_data.get("birth_date"):
            existing.birth_date = new_data["birth_date"]

        if not existing.birth_place and new_data.get("birth_place"):
            existing.birth_place = new_data["birth_place"]

        if not existing.birth_city and new_data.get("birth_city"):
            existing.birth_city = new_data["birth_city"]

        if not existing.birth_state and new_data.get("birth_state"):
            existing.birth_state = new_data["birth_state"]

        if not existing.birth_country and new_data.get("birth_country"):
            existing.birth_country = new_data["birth_country"]

        if not existing.death_date and new_data.get("death_date"):
            existing.death_date = new_data["death_date"]

        if not existing.death_place and new_data.get("death_place"):
            existing.death_place = new_data["death_place"]

        if not existing.sex and new_data.get("sex"):
            existing.sex = new_data["sex"]

        return existing

    def create_person_from_data(self, data: Dict) -> Person:
        """Create a new Person from normalized data"""
        person = Person(
            first_name=data.get("first_name", ""),
            middle_name=data.get("middle_name"),
            last_name=data.get("last_name", ""),
            birth_date=data.get("birth_date"),
            birth_place=data.get("birth_place"),
            birth_city=data.get("birth_city"),
            birth_state=data.get("birth_state"),
            birth_country=data.get("birth_country"),
            death_date=data.get("death_date"),
            death_place=data.get("death_place"),
            sex=data.get("sex"),
            confidence_score=100.0
        )
        return person

    def process_record(self, raw_record: RawPersonRecord) -> Person:
        """
        Process a raw person record:
        1. Find matches among existing persons
        2. Auto-merge if high confidence
        3. Create match candidate if medium confidence
        4. Create new person if no match
        """
        record_data = raw_record.normalized_data

        # Get all existing persons (in production, would use smarter querying)
        existing_persons = self.db.query(Person).all()

        # Find matches
        matches = self.find_matches_for_record(record_data, existing_persons)

        if not matches:
            # No match - create new person
            person = self.create_person_from_data(record_data)
            self.db.add(person)
            self.db.flush()  # Get person.id
            raw_record.matched_person_id = person.id
            raw_record.processed = True
            return person

        # Get best match
        best_match_person, best_score, match_details = matches[0]

        if self.matcher.should_auto_merge(best_score):
            # High confidence - auto merge
            person = self.merge_person_data(best_match_person, record_data)
            raw_record.matched_person_id = person.id
            raw_record.processed = True
            return person

        elif self.matcher.should_review(best_score):
            # Medium confidence - create match candidate for review
            # For now, still merge but flag it
            person = self.merge_person_data(best_match_person, record_data)
            raw_record.matched_person_id = person.id
            raw_record.processed = True

            # Create match candidate (in production would check if exists)
            match_candidate = MatchCandidate(
                person_a_id=best_match_person.id,
                person_b_id=best_match_person.id,  # Same person after merge
                similarity_score=best_score,
                match_details=match_details,
                match_status="auto_merged_review"
            )
            self.db.add(match_candidate)

            return person

        else:
            # Low confidence - create new person
            person = self.create_person_from_data(record_data)
            self.db.add(person)
            self.db.flush()
            raw_record.matched_person_id = person.id
            raw_record.processed = True
            return person
