"""Fuzzy matching service for person deduplication"""
from rapidfuzz import fuzz
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from app.config import get_settings

settings = get_settings()


class PersonMatcher:
    """Fuzzy matching logic for identifying duplicate persons"""

    @staticmethod
    def calculate_name_similarity(name1: Dict[str, str], name2: Dict[str, str]) -> float:
        """
        Calculate similarity between two names
        Returns: 0.0 to 1.0
        """
        # Compare full names
        full_name1 = f"{name1.get('first_name', '')} {name1.get('middle_name', '')} {name1.get('last_name', '')}".strip()
        full_name2 = f"{name2.get('first_name', '')} {name2.get('middle_name', '')} {name2.get('last_name', '')}".strip()

        if not full_name1 or not full_name2:
            return 0.0

        # Use token sort ratio for better matching (handles word order)
        similarity = fuzz.token_sort_ratio(full_name1.lower(), full_name2.lower()) / 100.0

        # Boost if last names are very similar
        last_name1 = name1.get('last_name', '').lower()
        last_name2 = name2.get('last_name', '').lower()
        if last_name1 and last_name2:
            last_name_sim = fuzz.ratio(last_name1, last_name2) / 100.0
            if last_name_sim > 0.9:
                similarity = similarity * 0.7 + last_name_sim * 0.3

        return similarity

    @staticmethod
    def calculate_date_proximity(date1, date2, max_years: int = None) -> float:
        """
        Calculate how close two dates are (accepts date objects or ISO strings)
        Returns: 0.0 to 1.0 (1.0 = exact match or both None)
        """
        from datetime import datetime as dt

        # Convert string dates to date objects
        if isinstance(date1, str):
            try:
                date1 = dt.fromisoformat(date1).date()
            except:
                date1 = None

        if isinstance(date2, str):
            try:
                date2 = dt.fromisoformat(date2).date()
            except:
                date2 = None

        if max_years is None:
            max_years = settings.date_proximity_years

        if date1 is None and date2 is None:
            return 1.0  # Both unknown = assume match

        if date1 is None or date2 is None:
            return 0.5  # One unknown = partial match

        # Exact match
        if date1 == date2:
            return 1.0

        # Calculate difference in days
        diff_days = abs((date1 - date2).days)
        max_days = max_years * 365

        if diff_days > max_days:
            return 0.0

        # Linear decay
        return 1.0 - (diff_days / max_days)

    @staticmethod
    def calculate_location_similarity(loc1: Optional[str], loc2: Optional[str]) -> float:
        """
        Calculate similarity between two location strings
        Returns: 0.0 to 1.0
        """
        if loc1 is None and loc2 is None:
            return 1.0

        if loc1 is None or loc2 is None:
            return 0.5

        loc1_clean = loc1.lower().strip()
        loc2_clean = loc2.lower().strip()

        if loc1_clean == loc2_clean:
            return 1.0

        # Partial match
        return fuzz.token_set_ratio(loc1_clean, loc2_clean) / 100.0

    @staticmethod
    def calculate_match_score(person1: Dict, person2: Dict) -> Tuple[float, Dict]:
        """
        Calculate overall match score between two persons
        Returns: (score, details_dict)
        """
        # Name similarity (40% weight)
        name1 = {
            "first_name": person1.get("first_name", ""),
            "middle_name": person1.get("middle_name", ""),
            "last_name": person1.get("last_name", "")
        }
        name2 = {
            "first_name": person2.get("first_name", ""),
            "middle_name": person2.get("middle_name", ""),
            "last_name": person2.get("last_name", "")
        }
        name_score = PersonMatcher.calculate_name_similarity(name1, name2)

        # Birth date proximity (30% weight)
        date_score = PersonMatcher.calculate_date_proximity(
            person1.get("birth_date"),
            person2.get("birth_date")
        )

        # Birth place similarity (20% weight)
        place_score = PersonMatcher.calculate_location_similarity(
            person1.get("birth_place"),
            person2.get("birth_place")
        )

        # Birth country match (10% weight) - must match if both known
        country_score = 1.0
        country1 = person1.get("birth_country")
        country2 = person2.get("birth_country")
        if country1 and country2:
            if country1.lower() == country2.lower():
                country_score = 1.0
            else:
                country_score = 0.0  # Hard fail if countries don't match
        else:
            country_score = 0.5  # Partial if one is unknown

        # Calculate weighted total
        total_score = (
            name_score * 0.40 +
            date_score * 0.30 +
            place_score * 0.20 +
            country_score * 0.10
        )

        details = {
            "name_score": round(name_score, 3),
            "date_score": round(date_score, 3),
            "place_score": round(place_score, 3),
            "country_score": round(country_score, 3),
            "total_score": round(total_score, 3)
        }

        return total_score, details

    @staticmethod
    def is_match(person1: Dict, person2: Dict, threshold: float = None) -> Tuple[bool, float, Dict]:
        """
        Determine if two persons are a match
        Returns: (is_match, score, details)
        """
        if threshold is None:
            threshold = settings.name_match_threshold

        score, details = PersonMatcher.calculate_match_score(person1, person2)
        return score >= threshold, score, details

    @staticmethod
    def should_auto_merge(score: float) -> bool:
        """Determine if match is confident enough to auto-merge"""
        return score >= settings.auto_merge_threshold

    @staticmethod
    def should_review(score: float) -> bool:
        """Determine if match should go to manual review queue"""
        return settings.manual_review_threshold <= score < settings.auto_merge_threshold
