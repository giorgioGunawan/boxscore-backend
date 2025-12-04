"""Team service with cache-aside pattern."""
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team
from app.nba_client import NBAClient
from app.cache import cache_get, cache_set, cache_delete_pattern
from app.config import get_settings

settings = get_settings()

# Module-level flag to avoid repeated checks
_teams_seeded = False


class TeamService:
    """Service for team-related operations."""
    
    @staticmethod
    async def ensure_teams_seeded(db: AsyncSession) -> None:
        """Ensure teams are seeded. Called automatically before team lookups."""
        global _teams_seeded
        
        if _teams_seeded:
            return
        
        # Check if teams exist
        result = await db.execute(select(func.count(Team.id)))
        count = result.scalar()
        
        if count == 0:
            print("🏀 Auto-seeding NBA teams...")
            await TeamService.seed_teams(db)
            print("✅ Teams seeded!")
        
        _teams_seeded = True
    
    @staticmethod
    async def get_all_teams(db: AsyncSession) -> list[dict]:
        """Get all teams from DB, seeding from NBA API if empty."""
        await TeamService.ensure_teams_seeded(db)
        
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
        await TeamService.ensure_teams_seeded(db)
        
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
        await TeamService.ensure_teams_seeded(db)
        
        result = await db.execute(select(Team).where(Team.nba_team_id == nba_team_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_team_by_abbreviation(db: AsyncSession, abbr: str) -> Optional[dict]:
        """Get team by abbreviation."""
        await TeamService.ensure_teams_seeded(db)
        
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
            # Check if team already exists (direct query, no ensure_teams_seeded)
            result = await db.execute(
                select(Team).where(Team.nba_team_id == team_data["nba_team_id"])
            )
            existing = result.scalar_one_or_none()
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
        await TeamService.ensure_teams_seeded(db)
        
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        return {t.nba_team_id: t.id for t in teams}
    
    @staticmethod
    async def get_team_abbr_map(db: AsyncSession) -> dict[str, int]:
        """Get mapping of team abbreviation to internal team ID."""
        await TeamService.ensure_teams_seeded(db)
        
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        return {t.abbreviation: t.id for t in teams}

