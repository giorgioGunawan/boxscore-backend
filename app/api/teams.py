"""Team API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import TeamService, GameService, StandingsService
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    """Get all NBA teams."""
    teams = await TeamService.get_all_teams(db)
    return {"teams": teams, "count": len(teams)}


@router.get("/{team_id}")
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Get team by ID."""
    team = await TeamService.get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/abbr/{abbreviation}")
async def get_team_by_abbr(abbreviation: str, db: AsyncSession = Depends(get_db)):
    """Get team by abbreviation (e.g., GSW, LAL)."""
    team = await TeamService.get_team_by_abbreviation(db, abbreviation)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/next-games")
async def get_next_games(
    team_id: int,
    count: int = Query(default=5, ge=1, le=20),
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get next N upcoming games for a team.
    
    - **team_id**: Internal team ID
    - **count**: Number of games to return (1-20, default 5)
    - **season**: Season string (e.g., "2024-25"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    """
    games = await GameService.get_next_games(
        db,
        team_id=team_id,
        count=count,
        season=season or settings.current_season,
        season_type=season_type,
        force_refresh=refresh,
    )
    return {"team_id": team_id, "games": games, "count": len(games)}


@router.get("/{team_id}/last-games")
async def get_last_games(
    team_id: int,
    count: int = Query(default=5, ge=1, le=20),
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get last N completed games for a team.
    
    - **team_id**: Internal team ID
    - **count**: Number of games to return (1-20, default 5)
    - **season**: Season string (e.g., "2024-25"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    """
    games = await GameService.get_last_games(
        db,
        team_id=team_id,
        count=count,
        season=season or settings.current_season,
        season_type=season_type,
        force_refresh=refresh,
    )
    return {"team_id": team_id, "games": games, "count": len(games)}


@router.get("/{team_id}/standings")
async def get_team_standings(
    team_id: int,
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get standings for a team.
    
    Returns team name, record (e.g., 11-11), and conference rank (e.g., 9th in West).
    
    - **team_id**: Internal team ID
    - **season**: Season string (e.g., "2024-25"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    """
    standing = await StandingsService.get_team_standing(
        db,
        team_id=team_id,
        season=season or settings.current_season,
        season_type=season_type,
        force_refresh=refresh,
    )
    if not standing:
        raise HTTPException(status_code=404, detail="Standings not found")
    return standing


@router.get("/standings/{conference}")
async def get_conference_standings(
    conference: str,
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full conference standings.
    
    - **conference**: "East" or "West"
    - **season**: Season string (e.g., "2024-25"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    """
    if conference.lower() not in ["east", "west"]:
        raise HTTPException(status_code=400, detail="Conference must be 'East' or 'West'")
    
    standings = await StandingsService.get_conference_standings(
        db,
        conference=conference.capitalize(),
        season=season or settings.current_season,
        season_type=season_type,
        force_refresh=refresh,
    )
    return {"conference": conference.capitalize(), "standings": standings}

