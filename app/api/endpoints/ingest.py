"""Ingest endpoint for loading genealogy records"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import IngestRequest, IngestResponse
from app.models import Source, ProcessingJob
from app.tasks.celery_tasks import process_records_task
from datetime import datetime

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_records(request: IngestRequest, db: Session = Depends(get_db)):
    """
    Ingest genealogy records from JSON
    Creates source records and queues background processing job
    """
    try:
        # Store each record as a source
        source_ids = []
        for record in request.records:
            source = Source(
                source_type=request.source_type,
                file_name=request.file_name,
                record_data=record
            )
            db.add(source)
            db.flush()
            source_ids.append(source.id)

        # Create processing job
        job = ProcessingJob(
            job_type="ingest_and_process",
            status="pending",
            total_records=len(request.records),
            result_data={"source_ids": source_ids}
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue Celery task for background processing
        process_records_task.delay(job.id, source_ids, request.source_type)

        return IngestResponse(
            job_id=job.id,
            message=f"Successfully queued {len(request.records)} records for processing",
            records_submitted=len(request.records),
            status="pending"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
