from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    nba_player_id = Column(Integer, unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    position = Column(String(20), nullable=True)
    
    # Relationships
    team = relationship("Team", back_populates="players")
    season_stats = relationship("PlayerSeasonStats", back_populates="player")
    game_stats = relationship("PlayerGameStats", back_populates="player")
    
    def __repr__(self):
        return f"<Player {self.full_name}>"

