from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    related_person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)  # parent, child, spouse, sibling
    confidence_score = Column(Float, default=100.0)
    source_id = Column(Integer, ForeignKey("sources.id"))

    # Relationships
    person = relationship("Person", foreign_keys=[person_id], back_populates="relationships_as_person")
    related_person = relationship("Person", foreign_keys=[related_person_id], back_populates="relationships_as_related")
    source = relationship("Source")

    def __repr__(self):
        return f"<Relationship(person_id={self.person_id}, related={self.related_person_id}, type='{self.relationship_type}')>"
