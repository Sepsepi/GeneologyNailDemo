from sqlalchemy import Column, Integer, String, Date, Float, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False, index=True)
    middle_name = Column(String(100))
    last_name = Column(String(100), nullable=False, index=True)
    birth_date = Column(Date, index=True)
    birth_place = Column(String(200))
    birth_city = Column(String(100))
    birth_state = Column(String(100))
    birth_country = Column(String(100), index=True)
    death_date = Column(Date)
    death_place = Column(String(200))
    sex = Column(String(1))  # M/F
    confidence_score = Column(Float, default=100.0)
    notes = Column(Text)

    # Relationships
    addresses = relationship("Address", back_populates="person", cascade="all, delete-orphan")
    relationships_as_person = relationship(
        "Relationship",
        foreign_keys="Relationship.person_id",
        back_populates="person",
        cascade="all, delete-orphan"
    )
    relationships_as_related = relationship(
        "Relationship",
        foreign_keys="Relationship.related_person_id",
        back_populates="related_person",
        cascade="all, delete-orphan"
    )
    raw_records = relationship("RawPersonRecord", back_populates="matched_person")

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.first_name} {self.last_name}', birth={self.birth_date})>"
