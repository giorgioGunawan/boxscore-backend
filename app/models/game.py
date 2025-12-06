from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Time, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    nba_game_id = Column(String(20), unique=True, nullable=True, index=True)  # nullable for manual entries
    season = Column(String(10), nullable=False, index=True)  # e.g., "2024-25"
    season_type = Column(String(30), nullable=False)  # Regular Season, Playoffs, etc.
    
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    
    # Date/time - store separately for easier manual editing
    game_date = Column(Date, nullable=True)
    game_time = Column(Time, nullable=True)
    timezone = Column(String(30), default="America/New_York")
    start_time_utc = Column(DateTime, nullable=True, index=True)  # Computed from date/time/tz
    
    status = Column(String(20), nullable=False, default="scheduled")  # scheduled, live, final, postponed
    
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    
    # Source tracking & override
    source = Column(String(20), default="api")  # 'api' or 'manual'
    is_manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    last_api_sync = Column(DateTime, nullable=True)
    last_manual_edit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    player_stats = relationship("PlayerGameStats", back_populates="game")
    
    def __repr__(self):
        return f"<Game {self.nba_game_id}: {self.away_team_id} @ {self.home_team_id}>"
