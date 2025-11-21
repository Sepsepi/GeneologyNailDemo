"""Jobs endpoint for monitoring processing status"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProcessingJob
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: int
    job_type: str
    status: str
    records_processed: int
    total_records: int
    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """Get the status of a processing job"""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        records_processed=job.records_processed,
        total_records=job.total_records,
        result_data=job.result_data,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at
    )
