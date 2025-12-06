#!/usr/bin/env python3
"""
Seed player season stats and latest game stats from NBA API.

This script fetches:
1. Season averages for all players (current season)
2. Latest game stats for all players (from most recent game)

Usage:
    python scripts/seed_player_stats.py              # Seed everything
    python scripts/seed_player_stats.py --season    # Season stats only
    python scripts/seed_player_stats.py --games     # Game stats only
"""

import asyncio
import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.database import AsyncSessionLocal, init_db
from app.models import Player, PlayerSeasonStats, PlayerGameStats, Game
from app.nba_client import NBAClient
from app.config import get_settings

settings = get_settings()


async def seed_player_season_stats(db):
    """Seed season stats for all players."""
    print("\n📈 Seeding player season stats...")
    
    # Get all players
    result = await db.execute(select(Player))
    players = result.scalars().all()
    
    if not players:
        print("   ⚠ No players found, run --players first")
        return
    
    print(f"   Found {len(players)} players, fetching season stats...")
    
    success = 0
    failed = 0
    skipped = 0
    
    for i, player in enumerate(players):
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i+1}/{len(players)}... (✓ {success}, ✗ {failed}, ⊘ {skipped})")
        
        try:
            # Fetch career stats from NBA API
            career_data = NBAClient.get_player_career_stats(player.nba_player_id)
            
            # Find current season stats
            season_data = None
            for s in career_data.get("seasons", []):
                if s["season"] == settings.current_season:
                    season_data = s
                    break
            
            if not season_data:
                skipped += 1
                continue
            
            # Check if stats exist
            result = await db.execute(
                select(PlayerSeasonStats).where(
                    PlayerSeasonStats.player_id == player.id,
                    PlayerSeasonStats.season == settings.current_season,
                    PlayerSeasonStats.season_type == "Regular Season",
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing (only if not manual override)
                if not existing.is_manual_override:
                    existing.pts = season_data["pts"]
                    existing.reb = season_data["reb"]
                    existing.ast = season_data["ast"]
                    existing.stl = season_data["stl"]
                    existing.blk = season_data["blk"]
                    existing.games_played = season_data["games_played"]
                    existing.minutes = season_data["minutes"]
                    existing.fg_pct = season_data.get("fg_pct")
                    existing.fg3_pct = season_data.get("fg3_pct")
                    existing.ft_pct = season_data.get("ft_pct")
                    existing.source = "api"
                    existing.last_api_sync = datetime.utcnow()
                else:
                    skipped += 1
                    continue
            else:
                # Create new
                stats = PlayerSeasonStats(
                    player_id=player.id,
                    season=settings.current_season,
                    season_type="Regular Season",
                    pts=season_data["pts"],
                    reb=season_data["reb"],
                    ast=season_data["ast"],
                    stl=season_data["stl"],
                    blk=season_data["blk"],
                    games_played=season_data["games_played"],
                    minutes=season_data["minutes"],
                    fg_pct=season_data.get("fg_pct"),
                    fg3_pct=season_data.get("fg3_pct"),
                    ft_pct=season_data.get("ft_pct"),
                    source="api",
                    last_api_sync=datetime.utcnow(),
                )
                db.add(stats)
            
            await db.commit()
            success += 1
            
            # Rate limiting - be nice to NBA API
            time.sleep(0.6)
            
        except Exception as e:
            failed += 1
            print(f"   ✗ Error for {player.full_name} (ID: {player.nba_player_id}): {e}")
            continue
    
    print(f"   ✓ Season stats seeded for {success} players ({failed} failed, {skipped} skipped)")


async def seed_player_game_stats(db):
    """Seed latest game stats for all players."""
    print("\n🎯 Seeding player latest game stats...")
    
    # Get all players
    result = await db.execute(select(Player))
    players = result.scalars().all()
    
    if not players:
        print("   ⚠ No players found, run --players first")
        return
    
    print(f"   Found {len(players)} players, fetching latest game stats...")
    
    success = 0
    failed = 0
    skipped = 0
    
    # Try current season first, then previous seasons
    seasons_to_try = [settings.current_season]
    try:
        year = int(settings.current_season.split("-")[0])
        for i in range(1, 3):  # Try up to 2 previous seasons
            prev_year = year - i
            prev_season = f"{prev_year}-{str(prev_year + 1)[-2:]}"
            seasons_to_try.append(prev_season)
    except (ValueError, IndexError):
        pass
    
    for i, player in enumerate(players):
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i+1}/{len(players)}... (✓ {success}, ✗ {failed}, ⊘ {skipped})")
        
        try:
            # Try to get game log from most recent season
            game_log = None
            actual_season = None
            
            for try_season in seasons_to_try:
                try:
                    game_log_data = NBAClient.get_player_game_log(
                        player.nba_player_id,
                        season=try_season,
                        season_type="Regular Season",
                    )
                    if game_log_data and len(game_log_data) > 0:
                        game_log = game_log_data[0]  # Most recent game
                        actual_season = try_season
                        break
                except Exception:
                    continue
            
            if not game_log:
                skipped += 1
                continue
            
            # Get or create the game
            nba_game_id = game_log.get("nba_game_id")
            if not nba_game_id:
                skipped += 1
                continue
            
            # Check if game exists
            result = await db.execute(
                select(Game).where(Game.nba_game_id == nba_game_id)
            )
            game = result.scalar_one_or_none()
            
            if not game:
                # Game doesn't exist, skip (we need the game to exist first)
                skipped += 1
                continue
            
            # Check if player game stats already exist
            result = await db.execute(
                select(PlayerGameStats).where(
                    PlayerGameStats.player_id == player.id,
                    PlayerGameStats.game_id == game.id,
                )
            )
            existing_stats = result.scalar_one_or_none()
            
            if existing_stats:
                # Update existing (only if not manual override)
                if not existing_stats.is_manual_override:
                    existing_stats.pts = game_log.get("pts", 0)
                    existing_stats.reb = game_log.get("reb", 0)
                    existing_stats.ast = game_log.get("ast", 0)
                    existing_stats.stl = game_log.get("stl", 0)
                    existing_stats.blk = game_log.get("blk", 0)
                    existing_stats.minutes = game_log.get("minutes")
                    existing_stats.fgm = game_log.get("fgm")
                    existing_stats.fga = game_log.get("fga")
                    existing_stats.fg3m = game_log.get("fg3m")
                    existing_stats.fg3a = game_log.get("fg3a")
                    existing_stats.ftm = game_log.get("ftm")
                    existing_stats.fta = game_log.get("fta")
                    existing_stats.plus_minus = game_log.get("plus_minus")
                    existing_stats.turnovers = game_log.get("turnovers")
                    existing_stats.source = "api"
                    existing_stats.last_api_sync = datetime.utcnow()
                else:
                    skipped += 1
                    continue
            else:
                # Create new
                stats = PlayerGameStats(
                    player_id=player.id,
                    game_id=game.id,
                    pts=game_log.get("pts", 0),
                    reb=game_log.get("reb", 0),
                    ast=game_log.get("ast", 0),
                    stl=game_log.get("stl", 0),
                    blk=game_log.get("blk", 0),
                    minutes=game_log.get("minutes"),
                    fgm=game_log.get("fgm"),
                    fga=game_log.get("fga"),
                    fg3m=game_log.get("fg3m"),
                    fg3a=game_log.get("fg3a"),
                    ftm=game_log.get("ftm"),
                    fta=game_log.get("fta"),
                    plus_minus=game_log.get("plus_minus"),
                    turnovers=game_log.get("turnovers"),
                    source="api",
                    last_api_sync=datetime.utcnow(),
                )
                db.add(stats)
            
            await db.commit()
            success += 1
            
            # Rate limiting - be nice to NBA API
            time.sleep(0.6)
            
        except Exception as e:
            failed += 1
            print(f"   ✗ Error for {player.full_name} (ID: {player.nba_player_id}): {e}")
            continue
    
    print(f"   ✓ Game stats seeded for {success} players ({failed} failed, {skipped} skipped)")


async def main():
    print("=" * 50)
    print("🏀 Player Stats Seeder")
    print(f"   Season: {settings.current_season}")
    print("=" * 50)
    
    # Parse args
    args = sys.argv[1:]
    seed_all = len(args) == 0
    
    # Initialize DB
    await init_db()
    
    async with AsyncSessionLocal() as db:
        if seed_all or "--season" in args:
            await seed_player_season_stats(db)
        
        if seed_all or "--games" in args:
            await seed_player_game_stats(db)
    
    print("\n" + "=" * 50)
    print("✅ Seeding complete!")
    print("=" * 50)
    
    # Print summary
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(PlayerSeasonStats.id)))
        season_stats = result.scalar_one()
        
        result = await db.execute(select(func.count(PlayerGameStats.id)))
        game_stats = result.scalar_one()
        
        print(f"\n📊 Database Summary:")
        print(f"   Season Stats: {season_stats}")
        print(f"   Game Stats:   {game_stats}")


if __name__ == "__main__":
    asyncio.run(main())

