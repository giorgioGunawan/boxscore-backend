#!/usr/bin/env python3
"""
Fix game times in database - subtract 5 hours from start_time_utc values
that were incorrectly stored as Eastern Time instead of UTC.

This script corrects the timezone issue where games were stored with Eastern Time
values but labeled as UTC, causing a 5-hour offset.
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.models.game import Game

async def fix_game_times():
    """Fix game times by subtracting 5 hours from incorrectly stored UTC values."""
    settings = get_settings()
    database_url = settings.database_url
    
    # Ensure async SQLite driver is used
    if database_url.startswith("sqlite:"):
        database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:")
    elif "postgresql:" in database_url and "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql:", "postgresql+asyncpg:")
    
    # Use async engine
    engine = create_async_engine(database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Get all games with start_time_utc
            result = await db.execute(select(Game).where(Game.start_time_utc.isnot(None)))
            games = result.scalars().all()
            
            print(f"Found {len(games)} games with start_time_utc")
            
            fixed_count = 0
            for game in games:
                if game.start_time_utc:
                    # Subtract 5 hours (the incorrect conversion from Eastern to UTC)
                    # If the time was stored as Eastern but labeled UTC, we need to subtract 5 hours
                    old_time = game.start_time_utc
                    new_time = old_time - timedelta(hours=5)
                    
                    game.start_time_utc = new_time
                    fixed_count += 1
                    
                    if fixed_count <= 5:
                        print(f"  Fixed: {old_time} -> {new_time} (Game ID: {game.id}, NBA ID: {game.nba_game_id})")
            
            await db.commit()
            print(f"\n✅ Fixed {fixed_count} game times")
            print("⚠️  Note: This assumes all times were incorrectly stored with +5 hours.")
            print("   If some games were already correct, you may need to re-sync from NBA API.")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error: {e}")
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    print("🔧 Fixing game times in database...")
    print("   This will subtract 5 hours from all start_time_utc values")
    print("   to correct the timezone issue.\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)
    
    asyncio.run(fix_game_times())

