from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # naturalization, obituary, census, etc.
    file_name = Column(String(200))
    record_data = Column(JSONB, nullable=False)  # Original JSON data
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Source(id={self.id}, type='{self.source_type}', file='{self.file_name}')>"


class RawPersonRecord(Base):
    """Records before deduplication - links to original source"""
    __tablename__ = "raw_person_records"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    normalized_data = Column(JSONB, nullable=False)  # Cleaned/normalized person data
    processed = Column(Boolean, default=False, index=True)
    matched_person_id = Column(Integer, ForeignKey("persons.id"), index=True)  # After deduplication
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source = relationship("Source")
    matched_person = relationship("Person", back_populates="raw_records")

    def __repr__(self):
        return f"<RawPersonRecord(id={self.id}, source_id={self.source_id}, matched={self.matched_person_id})>"
