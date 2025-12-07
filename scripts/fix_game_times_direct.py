"""
Script to directly fix game times by subtracting 5 hours from all existing games.
This fixes the timezone conversion bug where ET was incorrectly converted to UTC.
"""
import asyncio
import sys
import os
from datetime import timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models import Game

async def fix_all_game_times():
    """Fix all game times by subtracting 5 hours (EST offset)."""
    async with AsyncSessionLocal() as db:
        # Get all games with start_time_utc
        result = await db.execute(
            select(Game).where(Game.start_time_utc.isnot(None))
        )
        games = result.scalars().all()
        
        print(f"Found {len(games)} games with times. Fixing...")
        print("=" * 60)
        
        fixed_count = 0
        for idx, game in enumerate(games, 1):
            if game.start_time_utc:
                # Subtract 5 hours (EST offset that was incorrectly added)
                old_time = game.start_time_utc
                new_time = old_time - timedelta(hours=5)
                
                # Update the game
                await db.execute(
                    update(Game)
                    .where(Game.id == game.id)
                    .values(start_time_utc=new_time)
                )
                
                fixed_count += 1
                if idx % 100 == 0:
                    print(f"Fixed {idx} games...")
                    await db.commit()  # Commit in batches
        
        await db.commit()
        print("=" * 60)
        print(f"✅ Complete! Fixed {fixed_count} game times.")
        print("\nAll game times have been corrected (subtracted 5 hours).")


if __name__ == "__main__":
    asyncio.run(fix_all_game_times())

