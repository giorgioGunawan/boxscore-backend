from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    nba_team_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    abbreviation = Column(String(10), nullable=False)
    conference = Column(String(10), nullable=False)  # East, West
    division = Column(String(50), nullable=False)
    city = Column(String(50), nullable=True)
    
    # Source tracking & override
    source = Column(String(20), default="api")  # 'api' or 'manual'
    is_manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    last_api_sync = Column(DateTime, nullable=True)
    last_manual_edit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    players = relationship("Player", back_populates="team")
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    standings = relationship("TeamStandings", back_populates="team")
    
    def __repr__(self):
        return f"<Team {self.abbreviation} - {self.name}>"
