from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    nba_game_id = Column(String(20), unique=True, nullable=False, index=True)
    season = Column(String(10), nullable=False, index=True)  # e.g., "2024-25"
    season_type = Column(String(30), nullable=False)  # Regular Season, Playoffs, etc.
    
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    
    start_time_utc = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="scheduled")  # scheduled, in_progress, final
    
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    
    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    player_stats = relationship("PlayerGameStats", back_populates="game")
    
    def __repr__(self):
        return f"<Game {self.nba_game_id}: {self.away_team_id} @ {self.home_team_id}>"

