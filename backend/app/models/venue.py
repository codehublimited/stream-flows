from sqlalchemy import Column, Integer, String
from app.db.base import Base

class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    capacity = Column(Integer, nullable=True)