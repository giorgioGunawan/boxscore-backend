from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    nba_player_id = Column(Integer, unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    position = Column(String(20), nullable=True)
    jersey_number = Column(String(5), nullable=True)
    height = Column(String(10), nullable=True)
    weight = Column(String(10), nullable=True)
    
    # Source tracking & override
    source = Column(String(20), default="api")  # 'api' or 'manual'
    is_manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    last_api_sync = Column(DateTime, nullable=True)
    last_manual_edit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="players")
    season_stats = relationship("PlayerSeasonStats", back_populates="player")
    game_stats = relationship("PlayerGameStats", back_populates="player")
    
    def __repr__(self):
        return f"<Player {self.full_name}>"
