from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    api_id = Column(String, unique=True, index=True)
    position = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    nationality = Column(String, nullable=True)

    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="players")