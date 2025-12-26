"""
Script to update player rosters from NBA API.
This will add Cooper Flagg and other new players to the database.
"""
import asyncio
import sys
sys.path.insert(0, '/Users/giorgio/personal/boxscore-backend')

from app.database import AsyncSessionLocal
from app.models import Team, Player
from app.nba_client import NBAClient
from sqlalchemy import select


async def update_rosters():
    """Update all team rosters from NBA API."""
    print("🏀 Updating NBA team rosters...")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        # Get all teams
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        
        print(f"\n📊 Found {len(teams)} teams in database")
        print(f"🔄 Fetching rosters for 2025-26 season...\n")
        
        total_new = 0
        total_updated = 0
        
        for i, team in enumerate(teams, 1):
            print(f"[{i}/{len(teams)}] {team.abbreviation}...", end=" ")
            
            try:
                # Fetch roster from NBA API
                roster = NBAClient.get_team_roster(team.nba_team_id, season='2025-26')
                
                new_players = 0
                updated_players = 0
                
                for p_data in roster:
                    nba_id = p_data["nba_player_id"]
                    
                    # Check if player exists
                    res = await db.execute(
                        select(Player).where(Player.nba_player_id == nba_id)
                    )
                    player = res.scalar_one_or_none()
                    
                    if not player:
                        # Create new player
                        player = Player(
                            nba_player_id=nba_id,
                            full_name=p_data["name"],
                            team_id=team.id,
                            position=p_data.get("position"),
                            jersey_number=p_data.get("number")
                        )
                        db.add(player)
                        new_players += 1
                        
                        # Print new rookies/players
                        if "Flagg" in p_data["name"] or new_players <= 3:
                            print(f"\n   ✨ NEW: {p_data['name']} (#{p_data.get('number')})")
                    else:
                        # Update existing player's team
                        if player.team_id != team.id:
                            old_team_res = await db.execute(
                                select(Team).where(Team.id == player.team_id)
                            )
                            old_team = old_team_res.scalar_one_or_none()
                            old_abbr = old_team.abbreviation if old_team else "???"
                            print(f"\n   🔄 TRADED: {player.full_name} ({old_abbr} → {team.abbreviation})")
                            player.team_id = team.id
                            updated_players += 1
                
                await db.commit()
                
                total_new += new_players
                total_updated += updated_players
                
                if new_players > 0 or updated_players > 0:
                    print(f"✅ {len(roster)} players ({new_players} new, {updated_players} updated)")
                else:
                    print(f"✅ {len(roster)} players (no changes)")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
        
        print("\n" + "=" * 60)
        print(f"✅ COMPLETE!")
        print(f"   Total new players: {total_new}")
        print(f"   Total updated players: {total_updated}")
        
        # Check if Cooper Flagg was added
        result = await db.execute(
            select(Player).where(Player.nba_player_id == 1642843)
        )
        cooper = result.scalar_one_or_none()
        
        if cooper:
            print(f"\n🎉 Cooper Flagg successfully added!")
            print(f"   NBA Player ID: {cooper.nba_player_id}")
            print(f"   Name: {cooper.full_name}")
            print(f"   Team ID: {cooper.team_id}")
        else:
            print(f"\n⚠️ Cooper Flagg was NOT added (check Dallas Mavericks roster)")


if __name__ == '__main__':
    asyncio.run(update_rosters())
