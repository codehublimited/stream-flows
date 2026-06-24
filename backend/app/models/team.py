from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    api_id = Column(String, unique=True, index=True)
    logo = Column(String, nullable=True)

    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    league = relationship("League", back_populates="teams")
    
    # Add this relationship
    players = relationship("Player", back_populates="team")
alembic revision --autogenerate -m "remove notes test column"
alembic upgrade head
alembic current