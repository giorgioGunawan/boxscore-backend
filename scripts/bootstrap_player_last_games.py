import asyncio
import os
import sys
from datetime import datetime
from sqlalchemy import select, text

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import Player, PlayerGameStats, Game
from app.nba_client.client import NBAClient
from app.config import get_settings

settings = get_settings()

async def main():
    print("🚀 Starting Player Last Game Bootstrap...")
    print(f"📅 Season: {settings.current_season}")
    
    async with AsyncSessionLocal() as db:
        # Get all players
        result = await db.execute(select(Player))
        players = result.scalars().all()
        print(f"👥 Found {len(players)} players in database")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, player in enumerate(players, 1):
            try:
                print(f"[{i}/{len(players)}] Processing {player.full_name} ({player.nba_player_id})...", end="", flush=True)
                
                # Fetch game log
                loop = asyncio.get_event_loop()
                games = await loop.run_in_executor(
                    None, 
                    lambda: NBAClient.get_player_game_log(
                        player.nba_player_id, 
                        season=settings.current_season
                    )
                )
                
                if not games:
                    print(" ⚠️ No games found (Skipping)")
                    skipped_count += 1
                    continue
                
                # Sort by date descending (just in case API didn't)
                games.sort(key=lambda x: x["game_date"], reverse=True)
                latest_game_data = games[0]
                
                # Ensure the game exists in our DB (optional but good for FKs)
                # If we strictly need foreign keys, we must have the Game record.
                # The user just said "add their latest game into the table".
                # PlayerGameStats requires game_id (FK).
                # So we must check if Game exists, if not, create a dummy or fetch it?
                # Best approach: Check if Game exists. If not, maybe skip or insert basic Game record.
                # Given strict FKs, we better have the game.
                
                nba_game_id = latest_game_data["nba_game_id"]
                game_res = await db.execute(select(Game).where(Game.nba_game_id == nba_game_id))
                game = game_res.scalar_one_or_none()
                
                if not game:
                    # If game doesn't exist, we can't link FK. 
                    # Options: 
                    # 1. Fetch game info and create it.
                    # 2. Skip.
                    # Let's try to fetch basic game info to satisfy FK if possible, or just skip with warning.
                    print(f" ⚠️ Game {nba_game_id} not in DB. Fetching...", end="", flush=True)
                    # For now, let's create a minimal game record if missing?
                    # Or better, just skipping ensures data integrity if we assume `bootstrap_database` ran first.
                    # But the user said "running your bootstrap file didn't help", implies missing data.
                    # Let's Insert a minimal game record to allow stats storage.
                    game = Game(
                        nba_game_id=nba_game_id,
                        season=settings.current_season,
                        season_type=settings.current_season_type,
                        game_date=datetime.strptime(latest_game_data["game_date"], "%Y-%m-%d").date(),
                        status="final" # Assumption since it's in a log
                    )
                    db.add(game)
                    await db.flush() # Get ID
                    print(" Created.", end="", flush=True)

                # Now upsert PlayerGameStats
                # Check if stats exist
                stats_res = await db.execute(
                    select(PlayerGameStats).where(
                        PlayerGameStats.player_id == player.id,
                        PlayerGameStats.game_id == game.id
                    )
                )
                stats = stats_res.scalar_one_or_none()
                
                if not stats:
                    stats = PlayerGameStats(
                        player_id=player.id,
                        game_id=game.id
                    )
                    db.add(stats)
                
                # Update fields
                stats.pts = latest_game_data["pts"]
                stats.reb = latest_game_data["reb"]
                stats.ast = latest_game_data["ast"]
                stats.stl = latest_game_data["stl"]
                stats.blk = latest_game_data["blk"]
                stats.minutes = latest_game_data["minutes"]
                stats.fgm = latest_game_data["fgm"]
                stats.fga = latest_game_data["fga"]
                stats.fg3m = latest_game_data["fg3m"]
                stats.fg3a = latest_game_data["fg3a"]
                stats.ftm = latest_game_data["ftm"]
                stats.fta = latest_game_data["fta"]
                stats.plus_minus = latest_game_data["plus_minus"]
                stats.turnovers = latest_game_data["turnovers"]
                stats.last_api_sync = datetime.utcnow()
                
                print(f" ✅ Updated (PTS: {stats.pts})")
                updated_count += 1
                
                # Commit every 10 players
                if i % 10 == 0:
                    await db.commit()
                    
            except Exception as e:
                print(f" ❌ Error: {e}")
                error_count += 1
        
        await db.commit()
        print("\n🏁 Log Bootstrap Complete")
        print(f"   Updated: {updated_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Errors:  {error_count}")

if __name__ == "__main__":
    asyncio.run(main())
