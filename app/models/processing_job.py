from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.database import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False)  # ingest, deduplicate, match, score
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed
    records_processed = Column(Integer, default=0)
    total_records = Column(Integer, default=0)
    result_data = Column(JSONB)  # Stats, errors, etc.
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, type='{self.job_type}', status='{self.status}')>"
