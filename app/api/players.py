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

