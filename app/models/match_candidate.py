from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.database import Base


class MatchCandidate(Base):
    """Potential duplicate persons requiring manual review"""
    __tablename__ = "match_candidates"

    id = Column(Integer, primary_key=True, index=True)
    person_a_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    person_b_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    match_details = Column(JSONB)  # Breakdown of match scores
    match_status = Column(String(20), default="pending")  # pending, confirmed, rejected
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MatchCandidate(id={self.id}, a={self.person_a_id}, b={self.person_b_id}, score={self.similarity_score})>"
