"""Admin API endpoints."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Team, Player, Game, TeamStandings, PlayerSeasonStats, PlayerGameStats
from app.services import TeamService, StandingsService, GameService
from app.cache import get_cache_metrics, reset_cache_metrics, cache_delete_pattern
from app.config import get_settings
from app.nba_client import NBAClient

router = APIRouter()
settings = get_settings()

# Templates will be set up in main.py
templates: Optional[Jinja2Templates] = None


def set_templates(t: Jinja2Templates):
    global templates
    templates = t


# ============ API Endpoints ============

@router.get("/metrics")
async def get_metrics():
    """Get cache and API metrics."""
    return {
        "cache": get_cache_metrics(),
        "settings": {
            "current_season": settings.current_season,
            "cache_ttl_games": settings.cache_ttl_games,
            "cache_ttl_standings": settings.cache_ttl_standings,
            "cache_ttl_player_stats": settings.cache_ttl_player_stats,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset cache metrics."""
    reset_cache_metrics()
    return {"status": "ok", "message": "Metrics reset"}


@router.get("/stats")
async def get_database_stats(db: AsyncSession = Depends(get_db)):
    """Get database statistics."""
    # Count records in each table
    teams_count = await db.scalar(select(func.count(Team.id)))
    players_count = await db.scalar(select(func.count(Player.id)))
    games_count = await db.scalar(select(func.count(Game.id)))
    standings_count = await db.scalar(select(func.count(TeamStandings.id)))
    player_season_stats_count = await db.scalar(select(func.count(PlayerSeasonStats.id)))
    player_game_stats_count = await db.scalar(select(func.count(PlayerGameStats.id)))
    
    # Get latest game date
    latest_game = await db.scalar(
        select(func.max(Game.start_time_utc))
    )
    
    return {
        "tables": {
            "teams": teams_count or 0,
            "players": players_count or 0,
            "games": games_count or 0,
            "team_standings": standings_count or 0,
            "player_season_stats": player_season_stats_count or 0,
            "player_game_stats": player_game_stats_count or 0,
        },
        "latest_game_date": latest_game.isoformat() if latest_game else None,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/refresh/teams")
async def refresh_teams(db: AsyncSession = Depends(get_db)):
    """Seed/refresh all NBA teams."""
    count = await TeamService.seed_teams(db)
    return {"status": "ok", "teams_added": count}


@router.post("/refresh/standings")
async def refresh_standings(
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    db: AsyncSession = Depends(get_db)
):
    """Refresh standings for all teams."""
    count = await StandingsService.refresh_all_standings(
        db,
        season=season or settings.current_season,
        season_type=season_type,
    )
    return {"status": "ok", "standings_updated": count}


@router.post("/refresh/team/{team_id}/games")
async def refresh_team_games(
    team_id: int,
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    db: AsyncSession = Depends(get_db)
):
    """Refresh games for a specific team."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    count = await GameService.refresh_team_games(
        db,
        team=team,
        season=season or settings.current_season,
        season_type=season_type,
    )
    return {"status": "ok", "team": team.abbreviation, "games_added": count}


@router.post("/cache/clear")
async def clear_cache(pattern: str = Query(default="*")):
    """Clear cache entries matching pattern."""
    count = await cache_delete_pattern(pattern)
    return {"status": "ok", "keys_deleted": count}


@router.get("/teams/{team_id}/inspect")
async def inspect_team(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Inspect all data for a team."""
    # Get team
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get standings
    result = await db.execute(
        select(TeamStandings).where(
            TeamStandings.team_id == team_id,
            TeamStandings.season == settings.current_season,
        )
    )
    standings = result.scalar_one_or_none()
    
    # Get recent games
    result = await db.execute(
        select(Game)
        .where(
            (Game.home_team_id == team_id) | (Game.away_team_id == team_id),
            Game.season == settings.current_season,
        )
        .order_by(Game.start_time_utc.desc())
        .limit(10)
    )
    games = result.scalars().all()
    
    return {
        "team": {
            "id": team.id,
            "nba_team_id": team.nba_team_id,
            "name": team.name,
            "abbreviation": team.abbreviation,
            "conference": team.conference,
            "division": team.division,
        },
        "standings": {
            "wins": standings.wins,
            "losses": standings.losses,
            "conference_rank": standings.conference_rank,
            "streak": standings.streak,
        } if standings else None,
        "recent_games": [
            {
                "id": g.id,
                "nba_game_id": g.nba_game_id,
                "date": g.start_time_utc.isoformat(),
                "status": g.status,
                "home_score": g.home_score,
                "away_score": g.away_score,
            }
            for g in games
        ],
    }


@router.get("/players/{player_id}/inspect")
async def inspect_player(
    player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Inspect all data for a player."""
    # Get player
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get season stats
    result = await db.execute(
        select(PlayerSeasonStats).where(
            PlayerSeasonStats.player_id == player_id,
        )
    )
    season_stats = result.scalars().all()
    
    # Get recent game stats
    result = await db.execute(
        select(PlayerGameStats)
        .where(PlayerGameStats.player_id == player_id)
        .order_by(PlayerGameStats.id.desc())
        .limit(10)
    )
    game_stats = result.scalars().all()
    
    return {
        "player": {
            "id": player.id,
            "nba_player_id": player.nba_player_id,
            "full_name": player.full_name,
            "position": player.position,
            "team_id": player.team_id,
        },
        "season_stats": [
            {
                "season": s.season,
                "pts": s.pts,
                "reb": s.reb,
                "ast": s.ast,
                "games_played": s.games_played,
            }
            for s in season_stats
        ],
        "recent_game_stats": [
            {
                "game_id": gs.game_id,
                "pts": gs.pts,
                "reb": gs.reb,
                "ast": gs.ast,
                "minutes": gs.minutes,
            }
            for gs in game_stats
        ],
    }


# ============ Admin UI ============

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard HTML page."""
    if not templates:
        return HTMLResponse("<h1>Templates not configured</h1>")
    
    # Get stats
    teams_count = await db.scalar(select(func.count(Team.id)))
    players_count = await db.scalar(select(func.count(Player.id)))
    games_count = await db.scalar(select(func.count(Game.id)))
    
    # Get teams for dropdown
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    
    # Get cache metrics
    metrics = get_cache_metrics()
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "stats": {
                "teams": teams_count or 0,
                "players": players_count or 0,
                "games": games_count or 0,
            },
            "teams": teams,
            "metrics": metrics,
            "settings": {
                "current_season": settings.current_season,
            },
        }
    )

