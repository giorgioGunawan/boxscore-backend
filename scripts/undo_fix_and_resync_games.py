#!/usr/bin/env python3
"""
Undo the previous fix (add 5 hours back) and then re-sync all games from NBA API
with the correct UTC parsing logic.
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.models.game import Game
from app.services.game_service import GameService
from app.services.team_service import TeamService

async def undo_and_resync():
    """Undo previous fix and re-sync games."""
    settings = get_settings()
    database_url = settings.database_url
    
    # Ensure async SQLite driver is used
    if database_url.startswith("sqlite:"):
        database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:")
    elif "postgresql:" in database_url and "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql:", "postgresql+asyncpg:")
    
    engine = create_async_engine(database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print("Step 1: Undoing previous fix (adding 5 hours back)...")
            # Get all games with start_time_utc
            result = await db.execute(select(Game).where(Game.start_time_utc.isnot(None)))
            games = result.scalars().all()
            
            print(f"Found {len(games)} games with start_time_utc")
            
            undone_count = 0
            for game in games:
                if game.start_time_utc:
                    # Add 5 hours back (undoing the previous fix)
                    old_time = game.start_time_utc
                    new_time = old_time + timedelta(hours=5)
                    game.start_time_utc = new_time
                    undone_count += 1
                    
                    if undone_count <= 5:
                        print(f"  Undone: {old_time} -> {new_time} (Game ID: {game.id})")
            
            await db.commit()
            print(f"✅ Undone fix for {undone_count} games\n")
            
            print("Step 2: Re-syncing all games from NBA API with correct UTC parsing...")
            # Get all teams
            from app.models.team import Team
            teams_result = await db.execute(select(Team))
            teams = teams_result.scalars().all()
            
            print(f"Found {len(teams)} teams")
            
            resynced_count = 0
            for team in teams:
                try:
                    # Refresh schedule for this team
                    count = await GameService.refresh_team_schedule(
                        db, team, settings.current_season
                    )
                    resynced_count += count
                    print(f"  Resynced {count} games for {team.abbreviation}")
                except Exception as e:
                    print(f"  Error resyncing {team.abbreviation}: {e}")
            
            await db.commit()
            print(f"\n✅ Resynced {resynced_count} games total")
            print("⚠️  All games should now have correct UTC times from gameDateTimeUTC field")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    print("🔧 Undoing previous fix and re-syncing games with correct UTC parsing...")
    print("   This will:")
    print("   1. Add 5 hours back to all games (undoing previous fix)")
    print("   2. Re-sync all games from NBA API using gameDateTimeUTC field\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)
    
    asyncio.run(undo_and_resync())

