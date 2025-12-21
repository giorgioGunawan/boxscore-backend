"""Standings service with cache-aside pattern."""
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Team, TeamStandings
from app.nba_client import NBAClient
from app.cache import cache_get, cache_set, cache_delete_pattern
from app.config import get_settings
from app.services.team_service import TeamService

settings = get_settings()


class StandingsService:
    """Service for standings-related operations."""
    
    @staticmethod
    async def get_team_standing(
        db: AsyncSession,
        team_id: int,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> Optional[dict]:
        """
        Get standings for a specific team.
        """
        season = season or settings.current_season
        cache_key = f"team:{team_id}:standing:{season}:{season_type}"
        
        # Check cache first
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # Get team
        result = await db.execute(
            select(Team).where(Team.id == team_id)
        )
        team = result.scalar_one_or_none()
        
        if not team:
            return None
        
        # Check DB for standings
        result = await db.execute(
            select(TeamStandings).where(
                TeamStandings.team_id == team_id,
                TeamStandings.season == season,
                TeamStandings.season_type == season_type,
            )
        )
        standing = result.scalar_one_or_none()
        
        # If not in DB or forcing refresh, fetch from NBA API
        if not standing or force_refresh:
            await StandingsService.refresh_all_standings(db, season, season_type)
            
            # Re-query
            result = await db.execute(
                select(TeamStandings).where(
                    TeamStandings.team_id == team_id,
                    TeamStandings.season == season,
                    TeamStandings.season_type == season_type,
                )
            )
            standing = result.scalar_one_or_none()
        
        if not standing:
            return None
        
        response = {
            "team_id": team_id,
            "team_name": team.name,
            "team_abbreviation": team.abbreviation,
            "conference": team.conference,
            "season": season,
            "wins": standing.wins,
            "losses": standing.losses,
            "record": f"{standing.wins}-{standing.losses}",
            "conference_rank": standing.conference_rank,
            "conference_rank_display": _ordinal(standing.conference_rank),
            "division_rank": standing.division_rank,
            "win_pct": round(standing.win_pct * 100, 1) if standing.win_pct else None,
            "games_back": standing.games_back,
            "streak": standing.streak,
            "last_10": standing.last_10,
        }
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_standings)
        
        return response
    
    @staticmethod
    async def get_conference_standings(
        db: AsyncSession,
        conference: str,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> list[dict]:
        """
        Get standings for an entire conference.
        """
        season = season or settings.current_season
        cache_key = f"standings:{conference}:{season}:{season_type}"
        
        # Check cache first
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # Query standings from DB
        result = await db.execute(
            select(TeamStandings)
            .options(selectinload(TeamStandings.team))
            .join(Team)
            .where(
                TeamStandings.season == season,
                TeamStandings.season_type == season_type,
                Team.conference == conference,
            )
            .order_by(TeamStandings.conference_rank.asc())
        )
        standings = result.scalars().all()
        
        # If empty or forcing refresh, fetch from NBA API
        if not standings or force_refresh:
            await StandingsService.refresh_all_standings(db, season, season_type)
            
            # Re-query
            result = await db.execute(
                select(TeamStandings)
                .options(selectinload(TeamStandings.team))
                .join(Team)
                .where(
                    TeamStandings.season == season,
                    TeamStandings.season_type == season_type,
                    Team.conference == conference,
                )
                .order_by(TeamStandings.conference_rank.asc())
            )
            standings = result.scalars().all()
        
        response = []
        for standing in standings:
            team = standing.team
            response.append({
                "team_id": team.id,
                "team_name": team.name,
                "team_abbreviation": team.abbreviation,
                "conference": team.conference,
                "wins": standing.wins,
                "losses": standing.losses,
                "record": f"{standing.wins}-{standing.losses}",
                "conference_rank": standing.conference_rank,
                "conference_rank_display": _ordinal(standing.conference_rank),
                "win_pct": round(standing.win_pct * 100, 1) if standing.win_pct else None,
                "games_back": standing.games_back,
                "streak": standing.streak,
                "last_10": standing.last_10,
            })
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_standings)
        
        return response
    
    @staticmethod
    async def refresh_all_standings(
        db: AsyncSession,
        season: str,
        season_type: str,
        run_id: Optional[int] = None,
        details: Optional[dict] = None
    ) -> int:
        """
        Refresh standings for all teams from NBA API.
        Returns number of standings updated.
        """
        from app.services.cron_service import update_run_progress

        if run_id and details:
            details["logs"].append("   📡 Fetching latest standings from NBA API...")
            await update_run_progress(run_id, details, db_session=db)

        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        standings_data = await loop.run_in_executor(
            None,
            lambda: NBAClient.get_league_standings(
                season=season,
                season_type=season_type,
            )
        )
        
        if run_id and details:
            details["logs"].append(f"   ✓ received data for {len(standings_data)} teams")
            await update_run_progress(run_id, details, db_session=db)

        # Get team ID mapping
        team_id_map = await TeamService.get_team_id_map(db)
        
        # Bulk fetch existing standings to avoid N+1
        result = await db.execute(
            select(TeamStandings).where(
                TeamStandings.season == season,
                TeamStandings.season_type == season_type
            )
        )
        existing_standings_list = result.scalars().all()
        # Map by team_id for quick lookup
        existing_map = {s.team_id: s for s in existing_standings_list}

        count = 0
        total_teams = len(standings_data)
        
        for i, data in enumerate(standings_data):
            nba_team_id = data.get("nba_team_id")
            team_id = team_id_map.get(nba_team_id)
            
            if not team_id:
                continue
            
            # Progress update every 5 teams or at the end
            if run_id and details and (i % 5 == 0 or i == total_teams - 1):
                # Check for existing log to update instead of appending millions of lines
                progress_msg = f"   🔄 Processing standings: {i+1}/{total_teams} teams..."
                # Simple way: just append. The UI handles accumulating logs well.
                details["logs"].append(progress_msg)
                await update_run_progress(run_id, details, db_session=db)

            # Check if standing exists in our bulk-fetched map
            standing = existing_map.get(team_id)
            
            if standing:
                # Update
                standing.wins = data.get("wins", 0)
                standing.losses = data.get("losses", 0)
                standing.conference_rank = data.get("conference_rank", 0)
                standing.division_rank = data.get("division_rank")
                standing.win_pct = data.get("win_pct")
                standing.games_back = data.get("games_back")
                standing.streak = data.get("streak")
                standing.last_10 = data.get("last_10")
            else:
                # Create
                standing = TeamStandings(
                    team_id=team_id,
                    season=season,
                    season_type=season_type,
                    wins=data.get("wins", 0),
                    losses=data.get("losses", 0),
                    conference_rank=data.get("conference_rank", 0),
                    division_rank=data.get("division_rank"),
                    win_pct=data.get("win_pct"),
                    games_back=data.get("games_back"),
                    streak=data.get("streak"),
                    last_10=data.get("last_10"),
                )
                db.add(standing)
            
            count += 1
        
        await db.commit()
        
        # Invalidate standings cache
        await cache_delete_pattern("team:*:standing:*")
        await cache_delete_pattern("standings:*")
        
        return count


def _ordinal(n: int) -> str:
    """Convert number to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    return f"{n}{suffix}"

