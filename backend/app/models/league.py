from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    country = Column(String, nullable=True)
    api_id = Column(String, unique=True, index=True)
    logo = Column(String, nullable=True)

    teams = relationship("Team", back_populates="league")
    seasons = relationship("Season", back_populates="league")
