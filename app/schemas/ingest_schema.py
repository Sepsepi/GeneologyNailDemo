from pydantic import BaseModel
from typing import Any, Dict, List


class IngestRequest(BaseModel):
    source_type: str  # naturalization, obituary, census, immigration, birth
    file_name: str
    records: List[Dict[str, Any]]


class IngestResponse(BaseModel):
    job_id: int
    message: str
    records_submitted: int
    status: str
