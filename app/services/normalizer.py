"""Data normalization service for cleaning and standardizing genealogy records"""
from datetime import datetime
from dateutil import parser
from typing import Dict, Any, Optional
import re


class DataNormalizer:
    """Normalizes and cleans genealogy data from various sources"""

    @staticmethod
    def normalize_name(name: str) -> Dict[str, str]:
        """
        Parse and normalize a full name into components
        Returns: {first_name, middle_name, last_name}
        """
        if not name:
            return {"first_name": "", "middle_name": "", "last_name": ""}

        # Clean the name
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)  # Remove extra whitespace

        # Handle "LastName, FirstName MiddleName" format
        if ',' in name:
            parts = name.split(',', 1)
            last_name = parts[0].strip()
            first_middle = parts[1].strip().split()
        else:
            parts = name.split()
            if len(parts) == 0:
                return {"first_name": "", "middle_name": "", "last_name": ""}
            elif len(parts) == 1:
                return {"first_name": parts[0], "middle_name": "", "last_name": ""}
            else:
                first_middle = parts[:-1]
                last_name = parts[-1]

        first_name = first_middle[0] if first_middle else ""
        middle_name = ' '.join(first_middle[1:]) if len(first_middle) > 1 else ""

        return {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name
        }

    @staticmethod
    def normalize_date(date_value: Any) -> Optional[str]:
        """Parse various date formats into ISO format string (YYYY-MM-DD)"""
        if not date_value:
            return None

        if isinstance(date_value, datetime):
            return date_value.date().isoformat()

        if isinstance(date_value, str):
            try:
                return parser.parse(date_value).date().isoformat()
            except:
                return None

        return None

    @staticmethod
    def normalize_location(location: str) -> Dict[str, Optional[str]]:
        """
        Parse location string into components
        Returns: {city, state, country}
        """
        if not location:
            return {"city": None, "state": None, "country": None}

        parts = [p.strip() for p in location.split(',')]

        if len(parts) == 1:
            return {"city": parts[0], "state": None, "country": None}
        elif len(parts) == 2:
            return {"city": parts[0], "state": parts[1], "country": None}
        elif len(parts) >= 3:
            return {"city": parts[0], "state": parts[1], "country": parts[2]}

        return {"city": None, "state": None, "country": None}

    @staticmethod
    def extract_country(location: str) -> Optional[str]:
        """Extract just the country from a location string"""
        if not location:
            return None

        # Common patterns
        if "Germany" in location or "German" in location:
            return "Germany"
        if "Austria" in location:
            return "Austria"
        if "USA" in location or "United States" in location:
            return "United States"

        # Get last part after comma
        parts = [p.strip() for p in location.split(',')]
        return parts[-1] if parts else None

    @staticmethod
    def normalize_naturalization_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a naturalization record"""
        name_parts = DataNormalizer.normalize_name(record.get("petitioner_name", ""))
        birth_loc = DataNormalizer.normalize_location(record.get("birth_place", ""))

        return {
            "first_name": name_parts["first_name"],
            "middle_name": name_parts["middle_name"],
            "last_name": name_parts["last_name"],
            "birth_date": DataNormalizer.normalize_date(record.get("birth_date")),
            "birth_place": record.get("birth_place"),
            "birth_city": birth_loc["city"],
            "birth_state": birth_loc["state"],
            "birth_country": birth_loc["country"] or record.get("former_nationality"),
            "sex": None,
            "naturalization_date": DataNormalizer.normalize_date(record.get("naturalization_date")),
            "residence": record.get("residence_at_naturalization"),
            "source_data": record
        }

    @staticmethod
    def normalize_immigration_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an immigration record"""
        name_parts = DataNormalizer.normalize_name(record.get("passenger_name", ""))
        birth_loc = DataNormalizer.normalize_location(record.get("birthplace", ""))

        return {
            "first_name": name_parts["first_name"],
            "middle_name": name_parts["middle_name"],
            "last_name": name_parts["last_name"],
            "birth_date": DataNormalizer.normalize_date(record.get("birth_date")),
            "birth_place": record.get("birthplace"),
            "birth_city": birth_loc["city"],
            "birth_state": birth_loc["state"],
            "birth_country": DataNormalizer.extract_country(record.get("last_residence", "")),
            "sex": record.get("sex"),
            "arrival_date": DataNormalizer.normalize_date(record.get("arrival_date")),
            "source_data": record
        }

    @staticmethod
    def normalize_census_household_member(member: Dict[str, Any], address: str) -> Dict[str, Any]:
        """Normalize a census household member"""
        name_parts = DataNormalizer.normalize_name(member.get("name", ""))

        # Infer birth_date from age and census year if available
        birth_date = None
        if member.get("birth_year"):
            try:
                birth_date = datetime(int(member["birth_year"]), 1, 1).date().isoformat()
            except:
                pass

        return {
            "first_name": name_parts["first_name"],
            "middle_name": name_parts["middle_name"],
            "last_name": name_parts["last_name"],
            "birth_date": birth_date,
            "birth_place": member.get("birthplace"),
            "birth_country": DataNormalizer.extract_country(member.get("birthplace", "")),
            "sex": member.get("sex"),
            "residence": address,
            "source_data": member
        }

    @staticmethod
    def normalize_obituary_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an obituary record"""
        name_parts = DataNormalizer.normalize_name(record.get("deceased_name", ""))
        birth_loc = DataNormalizer.normalize_location(record.get("birth_place", ""))

        return {
            "first_name": name_parts["first_name"],
            "middle_name": name_parts["middle_name"],
            "last_name": name_parts["last_name"],
            "birth_date": DataNormalizer.normalize_date(record.get("birth_date")),
            "birth_place": record.get("birth_place"),
            "birth_city": birth_loc["city"],
            "birth_state": birth_loc["state"],
            "birth_country": birth_loc["country"],
            "death_date": DataNormalizer.normalize_date(record.get("death_date")),
            "death_place": record.get("death_place"),
            "last_residence": record.get("last_residence"),
            "sex": None,
            "source_data": record
        }

    @staticmethod
    def normalize_birth_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a birth record"""
        name_parts = DataNormalizer.normalize_name(record.get("child_name", ""))

        return {
            "first_name": name_parts["first_name"],
            "middle_name": name_parts["middle_name"],
            "last_name": name_parts["last_name"],
            "birth_date": DataNormalizer.normalize_date(record.get("birth_date")),
            "birth_place": record.get("birth_place"),
            "sex": record.get("sex"),
            "father_name": record.get("father_name"),
            "mother_name": record.get("mother_name"),
            "mother_maiden_name": record.get("mother_maiden_name"),
            "source_data": record
        }
