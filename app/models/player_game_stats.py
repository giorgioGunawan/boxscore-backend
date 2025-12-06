from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    
    # Box score stats
    pts = Column(Integer, nullable=False, default=0)
    reb = Column(Integer, nullable=False, default=0)
    ast = Column(Integer, nullable=False, default=0)
    stl = Column(Integer, nullable=False, default=0)
    blk = Column(Integer, nullable=False, default=0)
    minutes = Column(String(10), nullable=True)  # e.g., "34:22"
    
    # Additional stats
    fgm = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    fg3m = Column(Integer, nullable=True)
    fg3a = Column(Integer, nullable=True)
    ftm = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)
    plus_minus = Column(Integer, nullable=True)
    turnovers = Column(Integer, nullable=True)
    
    # Source tracking & override
    source = Column(String(20), default="api")  # 'api' or 'manual'
    is_manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    last_api_sync = Column(DateTime, nullable=True)
    last_manual_edit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    player = relationship("Player", back_populates="game_stats")
    game = relationship("Game", back_populates="player_stats")
    
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="uq_player_game_stats"),
    )
    
    def __repr__(self):
        return f"<PlayerGameStats {self.player_id} - Game {self.game_id}>"
