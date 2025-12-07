"""
Script to fix game times by refreshing all team schedules.
This will update all games with correct UTC times (fixing the 5-hour offset issue).
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Team
from app.services.game_service import GameService
from app.config import get_settings

settings = get_settings()


async def fix_all_game_times():
    """Refresh all team schedules to fix game times."""
    async with AsyncSessionLocal() as db:
        # Get all teams
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        
        print(f"Found {len(teams)} teams. Refreshing schedules...")
        print("=" * 60)
        
        total_games = 0
        for idx, team in enumerate(teams, 1):
            try:
                count = await GameService.refresh_team_schedule(
                    db, team, settings.current_season
                )
                total_games += count
                print(f"{idx:2d}. {team.abbreviation:3s} - Updated {count:3d} games")
            except Exception as e:
                print(f"{idx:2d}. {team.abbreviation:3s} - ERROR: {e}")
        
        await db.commit()
        print("=" * 60)
        print(f"✅ Complete! Updated {total_games} total games across {len(teams)} teams.")
        print("\nAll game times have been corrected to UTC.")


if __name__ == "__main__":
    asyncio.run(fix_all_game_times())

