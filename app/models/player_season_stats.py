from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class PlayerSeasonStats(Base):
    __tablename__ = "player_season_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(String(10), nullable=False, index=True)  # e.g., "2024-25"
    season_type = Column(String(30), nullable=False)
    
    # Per-game averages
    pts = Column(Float, nullable=False, default=0.0)
    reb = Column(Float, nullable=False, default=0.0)
    ast = Column(Float, nullable=False, default=0.0)
    stl = Column(Float, nullable=False, default=0.0)
    blk = Column(Float, nullable=False, default=0.0)
    
    # Additional useful stats
    games_played = Column(Integer, nullable=False, default=0)
    minutes = Column(Float, nullable=False, default=0.0)
    fg_pct = Column(Float, nullable=True)
    fg3_pct = Column(Float, nullable=True)
    ft_pct = Column(Float, nullable=True)
    
    # Relationships
    player = relationship("Player", back_populates="season_stats")
    
    __table_args__ = (
        UniqueConstraint("player_id", "season", "season_type", name="uq_player_season_stats"),
    )
    
    def __repr__(self):
        return f"<PlayerSeasonStats {self.player_id} - {self.season}>"

