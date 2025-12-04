"""Team service with cache-aside pattern."""
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team
from app.nba_client import NBAClient
from app.cache import cache_get, cache_set, cache_delete_pattern
from app.config import get_settings

settings = get_settings()


class TeamService:
    """Service for team-related operations."""
    
    @staticmethod
    async def get_all_teams(db: AsyncSession) -> list[dict]:
        """Get all teams from DB, seeding from NBA API if empty."""
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        
        if not teams:
            # Seed teams from NBA API
            await TeamService.seed_teams(db)
            result = await db.execute(select(Team))
            teams = result.scalars().all()
        
        return [
            {
                "id": t.id,
                "nba_team_id": t.nba_team_id,
                "name": t.name,
                "abbreviation": t.abbreviation,
                "conference": t.conference,
                "division": t.division,
            }
            for t in teams
        ]
    
    @staticmethod
    async def get_team_by_id(db: AsyncSession, team_id: int) -> Optional[dict]:
        """Get team by internal ID."""
        result = await db.execute(select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        
        if not team:
            return None
        
        return {
            "id": team.id,
            "nba_team_id": team.nba_team_id,
            "name": team.name,
            "abbreviation": team.abbreviation,
            "conference": team.conference,
            "division": team.division,
        }
    
    @staticmethod
    async def get_team_by_nba_id(db: AsyncSession, nba_team_id: int) -> Optional[Team]:
        """Get team by NBA team ID."""
        result = await db.execute(select(Team).where(Team.nba_team_id == nba_team_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_team_by_abbreviation(db: AsyncSession, abbr: str) -> Optional[dict]:
        """Get team by abbreviation."""
        result = await db.execute(
            select(Team).where(Team.abbreviation == abbr.upper())
        )
        team = result.scalar_one_or_none()
        
        if not team:
            return None
        
        return {
            "id": team.id,
            "nba_team_id": team.nba_team_id,
            "name": team.name,
            "abbreviation": team.abbreviation,
            "conference": team.conference,
            "division": team.division,
        }
    
    @staticmethod
    async def seed_teams(db: AsyncSession) -> int:
        """Seed all NBA teams into the database."""
        nba_teams = NBAClient.get_all_teams()
        count = 0
        
        for team_data in nba_teams:
            # Check if team already exists
            existing = await TeamService.get_team_by_nba_id(db, team_data["nba_team_id"])
            if existing:
                continue
            
            team = Team(
                nba_team_id=team_data["nba_team_id"],
                name=team_data["name"],
                abbreviation=team_data["abbreviation"],
                conference=team_data["conference"],
                division=team_data["division"],
            )
            db.add(team)
            count += 1
        
        await db.commit()
        return count
    
    @staticmethod
    async def get_team_id_map(db: AsyncSession) -> dict[int, int]:
        """Get mapping of NBA team ID to internal team ID."""
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        return {t.nba_team_id: t.id for t in teams}
    
    @staticmethod
    async def get_team_abbr_map(db: AsyncSession) -> dict[str, int]:
        """Get mapping of team abbreviation to internal team ID."""
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        return {t.abbreviation: t.id for t in teams}

