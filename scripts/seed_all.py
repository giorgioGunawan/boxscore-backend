#!/usr/bin/env python3
"""
Seed all NBA data: teams, players, schedules, and standings.

This script pre-populates the database with all known data so the API
doesn't need to fetch from NBA API on every request.

Usage:
    python scripts/seed_all.py              # Seed everything
    python scripts/seed_all.py --teams      # Seed teams only
    python scripts/seed_all.py --players    # Seed all players (from rosters)
    python scripts/seed_all.py --schedules  # Seed all team schedules
    python scripts/seed_all.py --standings  # Seed standings
"""

import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.database import AsyncSessionLocal, init_db
from app.models import Team, Player, Game, TeamStandings, PlayerSeasonStats
from app.nba_client import NBAClient
from app.services import TeamService, StandingsService, GameService
from app.config import get_settings

settings = get_settings()


async def seed_teams(db):
    """Seed all 30 NBA teams."""
    print("\n🏀 Seeding teams...")
    
    # Check if teams exist
    result = await db.execute(select(func.count(Team.id)))
    count = result.scalar_one()
    
    if count >= 30:
        print(f"   ✓ Teams already seeded ({count} teams)")
        return
    
    await TeamService.seed_teams(db)
    
    result = await db.execute(select(func.count(Team.id)))
    count = result.scalar_one()
    print(f"   ✓ Seeded {count} teams")


async def seed_standings(db):
    """Seed current standings for all teams."""
    print("\n📊 Seeding standings...")
    
    # Get all teams
    result = await db.execute(select(Team))
    teams = result.scalars().all()
    
    if not teams:
        print("   ⚠ No teams found, run --teams first")
        return
    
    # Fetch standings from NBA API
    print(f"   Fetching standings for season {settings.current_season}...")
    
    try:
        standings_data = NBAClient.get_league_standings(
            season=settings.current_season,
            season_type="Regular Season"
        )
        
        # Create team ID map
        team_nba_map = {t.nba_team_id: t for t in teams}
        
        count = 0
        for s in standings_data:
            team = team_nba_map.get(s["nba_team_id"])
            if not team:
                continue
            
            # Check if standings exist
            result = await db.execute(
                select(TeamStandings).where(
                    TeamStandings.team_id == team.id,
                    TeamStandings.season == settings.current_season,
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                existing.wins = s["wins"]
                existing.losses = s["losses"]
                existing.conference_rank = s["conference_rank"]
                existing.division_rank = s.get("division_rank")
                existing.win_pct = s.get("win_pct")
                existing.games_back = s.get("games_back")
                existing.streak = s.get("streak")
                existing.last_10 = s.get("last_10")
                existing.source = "api"
            else:
                # Create
                standing = TeamStandings(
                    team_id=team.id,
                    season=settings.current_season,
                    season_type="Regular Season",
                    wins=s["wins"],
                    losses=s["losses"],
                    conference_rank=s["conference_rank"],
                    division_rank=s.get("division_rank"),
                    win_pct=s.get("win_pct"),
                    games_back=s.get("games_back"),
                    streak=s.get("streak"),
                    last_10=s.get("last_10"),
                    source="api",
                )
                db.add(standing)
                count += 1
        
        await db.commit()
        print(f"   ✓ Seeded/updated standings for {len(standings_data)} teams")
        
    except Exception as e:
        print(f"   ✗ Error fetching standings: {e}")


async def seed_players(db):
    """Seed all players from team rosters."""
    print("\n👤 Seeding players from rosters...")
    
    # Get all teams
    result = await db.execute(select(Team))
    teams = result.scalars().all()
    
    if not teams:
        print("   ⚠ No teams found, run --teams first")
        return
    
    total_players = 0
    
    for i, team in enumerate(teams):
        print(f"   [{i+1}/{len(teams)}] {team.abbreviation}...", end="", flush=True)
        
        try:
            roster = NBAClient.get_team_roster(
                team.nba_team_id,
                season=settings.current_season
            )
            
            added = 0
            for p in roster:
                # Check if player exists
                result = await db.execute(
                    select(Player).where(Player.nba_player_id == p["nba_player_id"])
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update team assignment
                    existing.team_id = team.id
                    existing.position = p.get("position")
                    existing.jersey_number = p.get("number")
                    existing.height = p.get("height")
                    existing.weight = p.get("weight")
                else:
                    # Create new player
                    player = Player(
                        nba_player_id=p["nba_player_id"],
                        full_name=p["name"],
                        team_id=team.id,
                        position=p.get("position"),
                        jersey_number=p.get("number"),
                        height=p.get("height"),
                        weight=p.get("weight"),
                        source="api",
                    )
                    db.add(player)
                    added += 1
            
            await db.commit()
            print(f" ✓ {len(roster)} players ({added} new)")
            total_players += len(roster)
            
        except Exception as e:
            print(f" ✗ Error: {e}")
            continue
    
    print(f"   ✓ Total: {total_players} players processed")


async def seed_schedules(db):
    """Seed full season schedules for all teams."""
    print("\n📅 Seeding schedules...")
    
    # Get all teams
    result = await db.execute(select(Team))
    teams = result.scalars().all()
    
    if not teams:
        print("   ⚠ No teams found, run --teams first")
        return
    
    # Build team abbr map for lookups
    team_abbr_map = {t.abbreviation: t.id for t in teams}
    
    total_games = 0
    processed_game_ids = set()  # Track games we've already processed
    
    for i, team in enumerate(teams):
        print(f"   [{i+1}/{len(teams)}] {team.abbreviation}...", end="", flush=True)
        
        try:
            schedule = NBAClient.get_team_schedule(
                team.nba_team_id,
                season=settings.current_season
            )
            
            added = 0
            for game_data in schedule:
                nba_game_id = game_data["nba_game_id"]
                
                # Skip if we already processed this game
                if nba_game_id in processed_game_ids:
                    continue
                
                processed_game_ids.add(nba_game_id)
                
                # Check if game exists
                result = await db.execute(
                    select(Game).where(Game.nba_game_id == nba_game_id)
                )
                existing = result.scalar_one_or_none()
                
                # Get opponent team ID
                opponent_id = team_abbr_map.get(game_data["opponent_abbr"])
                if not opponent_id:
                    continue
                
                is_home = game_data["is_home"]
                home_team_id = team.id if is_home else opponent_id
                away_team_id = opponent_id if is_home else team.id
                
                # Parse game date and time
                # NOTE: gameTimeEst from NBA API is UTC (despite "Est" in name)
                from datetime import datetime, timezone
                try:
                    game_date_str = game_data["game_date"]
                    game_time_str = game_data.get("game_time", "00:00")
                    if game_time_str and game_time_str != "00:00":
                        # Parse as UTC (no conversion needed)
                        game_datetime = datetime.strptime(f"{game_date_str} {game_time_str}", "%Y-%m-%d %H:%M")
                        game_datetime = game_datetime.replace(tzinfo=timezone.utc).replace(tzinfo=None)
                    else:
                        game_datetime = datetime.strptime(game_date_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    continue
                
                status = game_data.get("status", "scheduled")
                home_score = game_data.get("home_score")
                away_score = game_data.get("away_score")
                
                # Convert scores
                if home_score is not None:
                    try:
                        home_score = int(home_score)
                    except:
                        home_score = None
                if away_score is not None:
                    try:
                        away_score = int(away_score)
                    except:
                        away_score = None
                
                if existing:
                    # Update
                    existing.status = status
                    if home_score is not None:
                        existing.home_score = home_score
                    if away_score is not None:
                        existing.away_score = away_score
                else:
                    # Create
                    game = Game(
                        nba_game_id=nba_game_id,
                        season=settings.current_season,
                        season_type="Regular Season",
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        start_time_utc=game_datetime,
                        status=status,
                        home_score=home_score,
                        away_score=away_score,
                        source="api",
                    )
                    db.add(game)
                    added += 1
                    total_games += 1
            
            await db.commit()
            print(f" ✓ {len(schedule)} games ({added} new)")
            
        except Exception as e:
            print(f" ✗ Error: {e}")
            continue
    
    # Get total games in DB
    result = await db.execute(select(func.count(Game.id)))
    db_count = result.scalar_one()
    print(f"   ✓ Total games in database: {db_count}")


async def seed_player_stats(db):
    """Seed season stats for all players in DB."""
    print("\n📈 Seeding player season stats...")
    
    # Get all players
    result = await db.execute(select(Player))
    players = result.scalars().all()
    
    if not players:
        print("   ⚠ No players found, run --players first")
        return
    
    print(f"   Found {len(players)} players, fetching stats...")
    
    success = 0
    failed = 0
    
    for i, player in enumerate(players):
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i+1}/{len(players)}...")
        
        try:
            career = NBAClient.get_player_career_stats(player.nba_player_id)
            
            # Find current season stats
            for season_data in career.get("seasons", []):
                if season_data["season"] != settings.current_season:
                    continue
                
                # Check if stats exist
                result = await db.execute(
                    select(PlayerSeasonStats).where(
                        PlayerSeasonStats.player_id == player.id,
                        PlayerSeasonStats.season == settings.current_season,
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update
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
                else:
                    # Create
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
                    )
                    db.add(stats)
                
                success += 1
                break
            
            await db.commit()
            
        except Exception as e:
            failed += 1
            continue
    
    print(f"   ✓ Stats seeded for {success} players ({failed} failed)")


async def main():
    print("=" * 50)
    print("🏀 NBA Data Seeder")
    print(f"   Season: {settings.current_season}")
    print("=" * 50)
    
    # Parse args
    args = sys.argv[1:]
    seed_all = len(args) == 0
    
    # Initialize DB
    await init_db()
    
    async with AsyncSessionLocal() as db:
        if seed_all or "--teams" in args:
            await seed_teams(db)
        
        if seed_all or "--standings" in args:
            await seed_standings(db)
        
        if seed_all or "--players" in args:
            await seed_players(db)
        
        if seed_all or "--schedules" in args:
            await seed_schedules(db)
        
        if "--stats" in args:
            # Only run if explicitly requested (takes a long time)
            await seed_player_stats(db)
    
    print("\n" + "=" * 50)
    print("✅ Seeding complete!")
    print("=" * 50)
    
    # Print summary
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(Team.id)))
        teams = result.scalar_one()
        
        result = await db.execute(select(func.count(Player.id)))
        players = result.scalar_one()
        
        result = await db.execute(select(func.count(Game.id)))
        games = result.scalar_one()
        
        result = await db.execute(select(func.count(TeamStandings.id)))
        standings = result.scalar_one()
        
        result = await db.execute(select(func.count(PlayerSeasonStats.id)))
        stats = result.scalar_one()
        
        print(f"\n📊 Database Summary:")
        print(f"   Teams:     {teams}")
        print(f"   Players:   {players}")
        print(f"   Games:     {games}")
        print(f"   Standings: {standings}")
        print(f"   Stats:     {stats}")


if __name__ == "__main__":
    asyncio.run(main())

