from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class TeamStandings(Base):
    __tablename__ = "team_standings"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    season = Column(String(10), nullable=False, index=True)
    season_type = Column(String(30), nullable=False)
    
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    conference_rank = Column(Integer, nullable=False)
    division_rank = Column(Integer, nullable=True)
    
    # Additional standings info
    win_pct = Column(Float, nullable=True)
    games_back = Column(Float, nullable=True)
    streak = Column(String(10), nullable=True)  # e.g., "W3", "L2"
    last_10 = Column(String(10), nullable=True)  # e.g., "7-3"
    
    # Source tracking & override
    source = Column(String(20), default="api")  # 'api' or 'manual'
    is_manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    last_api_sync = Column(DateTime, nullable=True)
    last_manual_edit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="standings")
    
    __table_args__ = (
        UniqueConstraint("team_id", "season", "season_type", name="uq_team_standings"),
    )
    
    def __repr__(self):
        return f"<TeamStandings {self.team_id} - {self.season}: {self.wins}-{self.losses}>"
