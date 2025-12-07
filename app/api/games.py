"""API endpoints for game and boxscore data."""
import asyncio
from fastapi import APIRouter, HTTPException
from app.nba_client import NBAClient

router = APIRouter(tags=["games"])


@router.get("/{game_id}/boxscore")
async def get_game_boxscore(game_id: str):
    """
    Get complete box score for a game including all player stats.
    
    Args:
        game_id: NBA game ID (e.g. "0022500351")
        
    Returns:
        Box score data with game status and all player stats
    """
    try:
        # Run the blocking NBA API call in a thread pool
        loop = asyncio.get_event_loop()
        boxscore_data = await loop.run_in_executor(
            None,
            NBAClient.get_game_boxscore_with_players,
            game_id
        )
        
        if not boxscore_data:
            raise HTTPException(
                status_code=404,
                detail=f"Box score not found for game {game_id}. Game may not exist or data not yet available."
            )
        
        return {
            "game_id": game_id,
            "game_status": boxscore_data.get("game_status"),
            "home_score": boxscore_data.get("home_score"),
            "away_score": boxscore_data.get("away_score"),
            "player_stats": boxscore_data.get("player_stats", []),
            "total_players": len(boxscore_data.get("player_stats", []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching box score: {str(e)}"
        )

