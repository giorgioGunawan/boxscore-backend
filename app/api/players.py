"""Player API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import PlayerService
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/search")
async def search_players(
    name: str = Query(..., min_length=2),
):
    """
    Search for players by name.
    
    Uses static NBA API data, no database lookup required.
    Returns NBA player IDs that can be used with other endpoints.
    
    Example: /api/players/search?name=curry
    """
    players = await PlayerService.search_players(name)
    return {"players": players, "count": len(players)}


@router.get("/{nba_player_id}/info")
async def get_player_info(
    nba_player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get player info by NBA player ID.
    
    Auto-creates player in database on first request.
    
    Example NBA IDs:
    - Stephen Curry: 201939
    - LeBron James: 2544
    - Jayson Tatum: 1628369
    """
    player = await PlayerService.get_or_create_player(db, nba_player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    return {
        "nba_player_id": player.nba_player_id,
        "full_name": player.full_name,
        "position": player.position,
        "team_id": player.team_id,
    }


@router.get("/{nba_player_id}/season-averages")
async def get_player_season_averages(
    nba_player_id: int,
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get player's season averages by NBA player ID.
    
    Returns PPG, APG, RPG, BPG, SPG for the specified season.
    Auto-creates player in database on first request.
    
    - **nba_player_id**: NBA player ID (e.g., 201939 for Curry)
    - **season**: Season string (e.g., "2025-26"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    
    Example: /api/players/201939/season-averages
    """
    try:
        # Auto-create player if needed
        player = await PlayerService.get_or_create_player(db, nba_player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        stats = await PlayerService.get_player_season_averages(
            db,
            player_id=player.id,
            season=season or settings.current_season,
            season_type=season_type,
            force_refresh=refresh,
        )
        if not stats:
            raise HTTPException(status_code=404, detail="Stats not found for this season")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting season averages for player {nba_player_id}: {e}")
        raise HTTPException(status_code=503, detail="NBA API temporarily unavailable, please try again")


@router.get("/{nba_player_id}/latest-game")
async def get_player_latest_game(
    nba_player_id: int,
    season: Optional[str] = Query(default=None),
    season_type: str = Query(default="Regular Season"),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get player's most recent game stats by NBA player ID.
    
    Returns stats like: 30 PTS, 15 REB, 4 AST vs LAL
    Auto-creates player in database on first request.
    
    - **nba_player_id**: NBA player ID (e.g., 201939 for Curry)
    - **season**: Season string (e.g., "2025-26"), defaults to current
    - **season_type**: "Regular Season" or "Playoffs"
    - **refresh**: Force refresh from NBA API
    
    Example: /api/players/201939/latest-game
    """
    try:
        # Auto-create player if needed
        player = await PlayerService.get_or_create_player(db, nba_player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        game = await PlayerService.get_player_latest_game(
            db,
            player_id=player.id,
            season=season or settings.current_season,
            season_type=season_type,
            force_refresh=refresh,
        )
        if not game:
            raise HTTPException(status_code=404, detail="No recent game found")
        return game
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting latest game for player {nba_player_id}: {e}")
        raise HTTPException(status_code=503, detail="NBA API temporarily unavailable, please try again")


@router.get("/roster")
async def get_player_roster(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all active NBA players with their current team relationships.
    
    Returns a complete roster of all players in the database with team information.
    Designed for iOS widgets that need up-to-date player-team relationships.
    
    Response is cached for 1 hour to optimize performance.
    
    Example: /api/players/roster
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.models.player import Player
    from app.models.team import Team
    from app.cache import cache_get, cache_set
    from fastapi.responses import JSONResponse
    
    # Check cache first
    cache_key = "player_roster_v1"
    cached_data = await cache_get(cache_key)
    if cached_data:
        return JSONResponse(
            content=cached_data,
            headers={"Cache-Control": "public, max-age=3600"}
        )
    
    try:
        # Query all players with team relationships
        query = (
            select(
                Player.nba_player_id,
                Player.full_name,
                Team.abbreviation,
                Team.name,
                Player.jersey_number,
                Player.position
            )
            .join(Team, Player.team_id == Team.id)
            .order_by(Player.full_name)
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        # Build player list
        players = []
        for row in rows:
            players.append({
                "nba_player_id": row.nba_player_id,
                "name": row.full_name,
                "team_abbreviation": row.abbreviation,
                "team_name": row.name,
                "jersey_number": row.jersey_number if row.jersey_number else None,
                "position": row.position if row.position else None
            })
        
        # Build response
        response_data = {
            "season": settings.current_season,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "total_players": len(players),
            "players": players
        }
        
        # Cache for 1 hour (3600 seconds)
        await cache_set(cache_key, response_data, ttl=3600)
        
        # Return with cache headers
        return JSONResponse(
            content=response_data,
            headers={"Cache-Control": "public, max-age=3600"}
        )
        
    except Exception as e:
        print(f"Error fetching player roster: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch player roster"
        )

