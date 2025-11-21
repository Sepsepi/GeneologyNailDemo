"""File conversion service using AI"""
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List
from openai import OpenAI
import os
import uuid
from datetime import datetime

class FileConverter:
    """Convert CSV/Excel/TXT files to genealogy JSON format using AI"""

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = "https://api.deepseek.com/v1" if os.getenv("DEEPSEEK_API_KEY") else None

        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY or OPENAI_API_KEY environment variable required")

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat" if base_url else "gpt-4"

    def convert_file(self, file_path: Path, record_type: str = "auto") -> Dict[str, Any]:
        """Convert file to JSON using AI"""
        # Read file content
        content = self._read_file(file_path)

        # Auto-detect record type if needed
        if record_type == "auto":
            record_type = self._detect_record_type(content)

        # Get schema for record type
        schema = self._get_schema(record_type)

        # Convert using AI
        converted_records = self._ai_convert(content, record_type, schema)

        # Generate proper unique record IDs
        converted_records = self._fix_record_ids(converted_records, file_path.stem, record_type)

        return {
            "records": converted_records,
            "record_type": record_type,
            "source_file": file_path.name
        }

    def _read_file(self, file_path: Path) -> str:
        """Read file content based on extension"""
        extension = file_path.suffix.lower()

        if extension == '.csv':
            df = pd.read_csv(file_path)
            return df.to_csv(index=False)

        elif extension in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
            return df.to_csv(index=False)

        elif extension == '.txt':
            with open(file_path) as f:
                return f.read()

        else:
            raise ValueError(f"Unsupported file type: {extension}")

    def _detect_record_type(self, content: str) -> str:
        """Auto-detect record type using AI"""
        prompt = f"""
Analyze this data and determine if it's:
- naturalization (citizenship petitions)
- immigration (port arrivals)
- census (household records)
- obituary (death notices)
- birth (birth certificates)

Data:
{content[:500]}

Return ONLY one word: naturalization, immigration, census, obituary, or birth
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        detected_type = response.choices[0].message.content.strip().lower()
        if detected_type not in ["naturalization", "immigration", "census", "obituary", "birth"]:
            detected_type = "naturalization"  # default

        return detected_type

    def _get_schema(self, record_type: str) -> str:
        """Get JSON schema for record type"""
        schemas = {
            "naturalization": """
{
  "record_id": "string",
  "petitioner_name": "string",
  "birth_date": "YYYY-MM-DD",
  "birth_place": "string",
  "naturalization_date": "YYYY-MM-DD",
  "former_nationality": "string",
  "court": "string"
}
""",
            "immigration": """
{
  "record_id": "string",
  "passenger_name": "string",
  "birth_date": "YYYY-MM-DD",
  "birthplace": "string",
  "arrival_date": "YYYY-MM-DD",
  "ship_name": "string",
  "port_of_arrival": "string",
  "destination": "string"
}
""",
            "census": """
{
  "record_id": "string",
  "household_head": "string",
  "birth_year": number,
  "birthplace": "string",
  "address": "string",
  "occupation": "string"
}
""",
            "obituary": """
{
  "record_id": "string",
  "deceased_name": "string",
  "birth_date": "YYYY-MM-DD",
  "birth_place": "string",
  "death_date": "YYYY-MM-DD",
  "last_address": "string"
}
""",
            "birth": """
{
  "record_id": "string",
  "child_name": "string",
  "birth_date": "YYYY-MM-DD",
  "birth_place": "string",
  "father_name": "string",
  "mother_name": "string"
}
"""
        }
        return schemas.get(record_type, schemas["naturalization"])

    def _ai_convert(self, content: str, record_type: str, schema: str) -> List[Dict]:
        """Use AI to convert data to JSON"""
        prompt = f"""
Convert this {record_type} data to JSON format.

Required JSON schema:
{schema}

Input data:
{content}

Instructions:
1. Extract all records from the data
2. Map fields to the schema
3. Use YYYY-MM-DD for dates
4. Create unique record_id if missing (use row number or generate)
5. Return ONLY a JSON array of objects, no markdown, no explanation

Example:
[
  {schema.strip()},
  ...
]
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            result_text = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            # Parse JSON
            records = json.loads(result_text)

            if not isinstance(records, list):
                raise ValueError("AI did not return a list")

            return records

        except Exception as e:
            raise ValueError(f"AI conversion failed: {str(e)}")

    def _fix_record_ids(self, records: List[Dict], filename: str, record_type: str) -> List[Dict]:
        """Generate proper unique record IDs"""
        # Create prefix based on record type
        type_prefixes = {
            "naturalization": "NAT",
            "immigration": "IMM",
            "census": "CEN",
            "obituary": "OBI",
            "birth": "BRT"
        }
        prefix = type_prefixes.get(record_type, "REC")

        # Get timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M")

        # Clean filename (remove extension, special chars)
        clean_filename = "".join(c for c in filename if c.isalnum())[:8].upper()

        # Generate unique IDs for each record
        for i, record in enumerate(records, 1):
            # Format: PREFIX-TIMESTAMP-FILENAME-SEQNUM
            # Example: IMM-202511201045-MESSY-001
            record["record_id"] = f"{prefix}-{timestamp}-{clean_filename}-{i:03d}"

        return records
