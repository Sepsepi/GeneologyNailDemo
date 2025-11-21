from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    street = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    from_date = Column(Date)
    to_date = Column(Date)
    source_id = Column(Integer, ForeignKey("sources.id"))

    # Relationships
    person = relationship("Person", back_populates="addresses")
    source = relationship("Source")

    def __repr__(self):
        return f"<Address(person_id={self.person_id}, city='{self.city}', state='{self.state}')>"
