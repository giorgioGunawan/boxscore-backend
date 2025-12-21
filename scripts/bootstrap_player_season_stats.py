import asyncio
import os
import sys
from datetime import datetime
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import Player, PlayerSeasonStats
from app.nba_client.client import NBAClient
from app.config import get_settings

settings = get_settings()

async def main():
    print("🚀 Starting Player Season Stats Bootstrap...")
    print(f"📅 Season: {settings.current_season}")
    
    async with AsyncSessionLocal() as db:
        # Get all players
        result = await db.execute(select(Player))
        players = result.scalars().all()
        print(f"👥 Found {len(players)} players in database")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process in chunks to avoid overwhelming rate limits/connection
        # But for this standalone script, serial is fine for reliability as requested.
        
        for i, player in enumerate(players, 1):
            try:
                print(f"[{i}/{len(players)}] Processing {player.full_name} ({player.nba_player_id})...", end="", flush=True)
                
                # Fetch season stats
                loop = asyncio.get_event_loop()
                # NBAClient.get_player_info returns generic info.
                # NBAClient.get_player_season_stats returns a dict with "seasons" list.
                stats_data = await loop.run_in_executor(
                    None, 
                    lambda: NBAClient.get_player_season_stats(
                        player.nba_player_id
                    )
                )
                
                if not stats_data or not stats_data.get("seasons"):
                    print(" ⚠️ No stats found (Skipping)")
                    skipped_count += 1
                    continue
                
                # Find current season in the list
                current_season_stats = None
                for s in stats_data["seasons"]:
                    if s["season_id"] == settings.current_season:
                        current_season_stats = s
                        break
                
                if not current_season_stats:
                    print(f" ⚠️ No stats for {settings.current_season} (Skipping)")
                    skipped_count += 1
                    continue
                
                # Upsert PlayerSeasonStats
                res = await db.execute(
                    select(PlayerSeasonStats).where(
                        PlayerSeasonStats.player_id == player.id,
                        PlayerSeasonStats.season == settings.current_season
                    )
                )
                stats = res.scalar_one_or_none()
                
                if not stats:
                    stats = PlayerSeasonStats(
                        player_id=player.id,
                        season=settings.current_season
                    )
                    db.add(stats)
                
                # Update fields
                stats.team_id = player.team_id # Link to current team
                stats.games_played = current_season_stats.get("gp", 0)
                stats.pts = current_season_stats.get("pts", 0)
                stats.reb = current_season_stats.get("reb", 0)
                stats.ast = current_season_stats.get("ast", 0)
                stats.stl = current_season_stats.get("stl", 0)
                stats.blk = current_season_stats.get("blk", 0)
                stats.fg_pct = current_season_stats.get("fg_pct", 0)
                stats.fg3_pct = current_season_stats.get("fg3_pct", 0)
                stats.ft_pct = current_season_stats.get("ft_pct", 0)
                # Keep minutes as float if possible or string? Model usually expects float for averages.
                # Checking model... assuming float or number. get_player_season_stats returns "min" usually as number.
                stats.minutes = current_season_stats.get("min", 0)
                
                stats.last_api_sync = datetime.utcnow()
                
                print(f" ✅ Updated (PPG: {stats.pts})")
                updated_count += 1
                
                # Commit every 10 players
                if i % 10 == 0:
                    await db.commit()
                    
            except Exception as e:
                print(f" ❌ Error: {e}")
                error_count += 1
        
        await db.commit()
        print("\n🏁 Season Stats Bootstrap Complete")
        print(f"   Updated: {updated_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Errors:  {error_count}")

if __name__ == "__main__":
    asyncio.run(main())
