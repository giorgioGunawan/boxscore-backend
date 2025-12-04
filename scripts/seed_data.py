#!/usr/bin/env python3
"""
Seed script to populate initial data.
Run this after starting the database to seed teams and standings.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, init_db
from app.services import TeamService, StandingsService
from app.config import get_settings

settings = get_settings()


async def seed_all():
    """Seed all initial data."""
    print("🏀 NBA Boxscore Backend - Data Seeder")
    print("=" * 50)
    
    # Initialize database tables
    print("\n📦 Initializing database tables...")
    await init_db()
    print("✅ Tables created")
    
    async with AsyncSessionLocal() as db:
        # Seed teams
        print("\n🏟️  Seeding NBA teams...")
        teams_added = await TeamService.seed_teams(db)
        print(f"✅ {teams_added} teams added")
        
        # Refresh standings
        print(f"\n📊 Fetching standings for {settings.current_season}...")
        standings_count = await StandingsService.refresh_all_standings(
            db,
            season=settings.current_season,
            season_type="Regular Season"
        )
        print(f"✅ {standings_count} team standings updated")
        
        # Show summary
        teams = await TeamService.get_all_teams(db)
        print(f"\n📋 Summary:")
        print(f"   - Total teams: {len(teams)}")
        print(f"   - Season: {settings.current_season}")
        
        print("\n✨ Seeding complete!")
        print("\nNext steps:")
        print("  1. Start the server: uvicorn app.main:app --reload")
        print("  2. Open admin console: http://localhost:8000/api/admin/")
        print("  3. Use the API: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(seed_all())

