#!/usr/bin/env python3
"""
Quick test to verify the team ID lookup fix.
This simulates what happens in the update_players_team cron job.
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Team

async def test_team_lookup():
    """Test that we can find teams by nba_team_id."""
    test_team_ids = [
        1610612744,  # GSW - Stephen Curry's team
        1610612737,  # ATL - Trae Young's team
        1610612738,  # BOS - Jayson Tatum's team
        1610612739,  # CLE - Darius Garland's team
    ]
    
    async with AsyncSessionLocal() as db:
        print("Testing team lookups...")
        for nba_team_id in test_team_ids:
            # Test with direct int
            result = await db.execute(
                select(Team).where(Team.nba_team_id == nba_team_id)
            )
            team = result.scalar_one_or_none()
            
            if team:
                print(f"✅ Found team {nba_team_id}: {team.abbreviation} - {team.name}")
            else:
                print(f"❌ Team {nba_team_id} NOT FOUND!")
        
        # Test with int() conversion (simulating what we added)
        print("\nTesting with int() conversion...")
        for nba_team_id in test_team_ids:
            # Simulate pandas returning the value
            nba_team_id_converted = int(nba_team_id) if nba_team_id else None
            
            result = await db.execute(
                select(Team).where(Team.nba_team_id == nba_team_id_converted)
            )
            team = result.scalar_one_or_none()
            
            if team:
                print(f"✅ Found team {nba_team_id_converted}: {team.abbreviation} - {team.name}")
            else:
                print(f"❌ Team {nba_team_id_converted} NOT FOUND!")

if __name__ == "__main__":
    asyncio.run(test_team_lookup())
