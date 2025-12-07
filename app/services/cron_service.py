"""Cron job service for scheduled data updates."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Game, Team, TeamStandings, Player, PlayerGameStats, 
    PlayerSeasonStats, CronJob, CronRun
)
from app.nba_client import NBAClient
from app.config import get_settings
from app.services import TeamService, StandingsService, GameService
from app.database import AsyncSessionLocal

settings = get_settings()


async def update_run_progress(run_id: int, details: Dict[str, Any]):
    """Update CronRun details during execution for real-time progress tracking."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(CronRun).where(CronRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.details = details
                await db.flush()  # Flush immediately
                await db.commit()
                print(f"[update_run_progress] Updated progress for run {run_id}, logs count: {len(details.get('logs', []))}")
    except Exception as e:
        print(f"[update_run_progress] Failed to update progress for run {run_id}: {e}")
        import traceback
        traceback.print_exc()


class CronService:
    """Service for managing cron jobs and scheduled updates."""
    
    @staticmethod
    async def update_finished_games(
        run_id: int,
        cancellation_token: Optional[Any] = None,
        hours_back: int = 7
    ) -> Dict[str, Any]:
        """
        Check for games finished in the last X hours and update:
        - Game results (scores)
        - Team standings for both teams
        - Player last game stats
        """
        print(f"[update_finished_games] Function called with run_id: {run_id}")
        
        start_time = datetime.now(timezone.utc)
        details = {
            "games_updated": 0,
            "standings_updated": [],
            "player_stats_updated": 0,
            "errors": [],
            "logs": []  # Add logs array for Live logs
        }
        
        print(f"[update_finished_games] Creating database session...")
        
        # Create our own database session
        async with AsyncSessionLocal() as db:
            try:
                print(f"[update_finished_games] Database session created, starting job logic...")
                
                # Check for cancellation before starting
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"].append(f"🔍 Starting update_finished_games job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"[update_finished_games] Added first log entry")
                
                # Find games that started in the past and might have finished
                # NOTE: Database stores naive datetimes (no timezone), but they represent UTC
                now = datetime.now(timezone.utc)
                time_window_ago = now - timedelta(hours=hours_back)
                
                # Convert to naive datetime for database comparison (SQLite doesn't handle timezones)
                now_naive = now.replace(tzinfo=None)
                time_window_ago_naive = time_window_ago.replace(tzinfo=None)
                
                details["logs"].append(f"📅 Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                details["logs"].append(f"📅 Looking for games that started in the last {hours_back} hours (between {time_window_ago.strftime('%Y-%m-%d %H:%M:%S')} and {now.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
                
                # Update progress immediately so logs appear
                await update_run_progress(run_id, details)
                
                # First, let's see how many games we have in total and in the past
                total_games_result = await db.execute(select(func.count(Game.id)))
                total_games = total_games_result.scalar()
                
                past_games_result = await db.execute(
                    select(func.count(Game.id)).where(Game.start_time_utc <= now_naive)
                )
                past_games = past_games_result.scalar()
                
                future_games_result = await db.execute(
                    select(func.count(Game.id)).where(Game.start_time_utc > now_naive)
                )
                future_games = future_games_result.scalar()
                
                details["logs"].append(f"📊 Total games in database: {total_games}")
                details["logs"].append(f"   • Games in the past: {past_games}")
                details["logs"].append(f"   • Games in the future: {future_games}")
                
                # Get games closest to NOW (most recent past games)
                # Sort by how close they are to now (ascending distance from now)
                result = await db.execute(
                    select(Game).where(Game.start_time_utc <= now_naive).order_by(Game.start_time_utc.desc()).limit(10).options(selectinload(Game.home_team), selectinload(Game.away_team))
                )
                past_latest_games = result.scalars().all()
                
                if past_latest_games:
                    details["logs"].append(f"📊 Most recent {len(past_latest_games)} games (closest to now):")
                    for idx, g in enumerate(past_latest_games[:5], 1):  # Show first 5
                        home_abbr = g.home_team.abbreviation if g.home_team else "???"
                        away_abbr = g.away_team.abbreviation if g.away_team else "???"
                        game_time = g.start_time_utc.strftime('%Y-%m-%d %H:%M:%S') if g.start_time_utc else "No time"
                        # Compare naive datetimes
                        hours_ago = (now_naive - g.start_time_utc).total_seconds() / 3600 if g.start_time_utc else 0
                        details["logs"].append(f"   {idx}. {away_abbr} @ {home_abbr}: {game_time} UTC ({hours_ago:.1f}h ago, Status: {g.status})")
                    if len(past_latest_games) > 5:
                        details["logs"].append(f"   ... and {len(past_latest_games) - 5} more")
                    
                    # Show the time gap
                    if past_latest_games[0].start_time_utc:
                        # Compare naive datetimes
                        most_recent_hours_ago = (now_naive - past_latest_games[0].start_time_utc).total_seconds() / 3600
                        if most_recent_hours_ago > 24:
                            details["logs"].append(f"⚠️ Most recent game was {most_recent_hours_ago:.1f} hours ago (outside our 24-hour window)")
                        else:
                            details["logs"].append(f"✓ Most recent game was {most_recent_hours_ago:.1f} hours ago (within our 24-hour window)")
                else:
                    details["logs"].append(f"⚠️ No games in the past found! All {total_games} games are scheduled for the future.")
                    details["logs"].append(f"ℹ️ Current season is {settings.current_season}. Make sure games have been seeded for the current date.")
                
                await update_run_progress(run_id, details)
                
                # Get all games that started in the specified time window (regardless of status)
                result = await db.execute(
                    select(Game).where(
                        Game.start_time_utc >= time_window_ago_naive,
                        Game.start_time_utc <= now_naive
                    ).options(selectinload(Game.home_team), selectinload(Game.away_team))
                )
                recent_games = result.scalars().all()
                
                details["logs"].append(f"📊 Found {len(recent_games)} games that started in the last {hours_back} hours (within our search window)")
                
                # Update progress
                await update_run_progress(run_id, details)
                
                # Early exit if no games found
                if not recent_games:
                    details["logs"].append(f"✅ No games found in the last {hours_back} hours. Exiting early.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details)
                    return {
                        "status": "success",
                        "items_updated": 0,
                        "details": details
                    }
                
                # Filter to games that are finished or should be finished
                # Games that started 2+ hours ago should be done by now
                two_hours_ago = now - timedelta(hours=2)
                two_hours_ago_naive = two_hours_ago.replace(tzinfo=None)
                games_to_check = []
                games_skipped_recent = []
                games_skipped_already_final = []
                
                for g in recent_games:
                    # Compare with naive datetimes
                    if g.start_time_utc <= two_hours_ago_naive or g.status == "final":
                        games_to_check.append(g)
                    elif g.start_time_utc > two_hours_ago_naive:
                        games_skipped_recent.append(g)
                    elif g.status == "final":
                        games_skipped_already_final.append(g)
                
                details["logs"].append(f"🎯 Filtering games:")
                details["logs"].append(f"   • {len(games_to_check)} games to check (started 2+ hours ago or already final)")
                if games_skipped_recent:
                    details["logs"].append(f"   • {len(games_skipped_recent)} games skipped (too recent, started <2 hours ago)")
                if games_skipped_already_final:
                    details["logs"].append(f"   • {len(games_skipped_already_final)} games skipped (already final)")
                
                if not games_to_check:
                    details["logs"].append("✅ No finished games found. All recent games are still in progress.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details)
                    return {
                        "status": "success",
                        "items_updated": 0,
                        "details": details
                    }
                
                teams_to_update = set()
                final_games = []  # Track which games were actually marked as final
                
                # Log each game being checked
                details["logs"].append("")
                details["logs"].append(f"🏀 Processing {len(games_to_check)} games:")
                for idx, game in enumerate(games_to_check, 1):
                    home_abbr = game.home_team.abbreviation if game.home_team else "???"
                    away_abbr = game.away_team.abbreviation if game.away_team else "???"
                    # Use naive datetime for comparison
                    hours_ago = (now_naive - game.start_time_utc).total_seconds() / 3600
                    details["logs"].append(f"   [{idx}/{len(games_to_check)}] {away_abbr} @ {home_abbr} - Status: {game.status}, Started {hours_ago:.1f}h ago")
                
                # Fetch all boxscores in parallel for games that need updates
                details["logs"].append("")
                games_needing_update = [g for g in games_to_check if g.status != "final" or g.home_score is None]
                
                if games_needing_update:
                    details["logs"].append(f"📡 Fetching {len(games_needing_update)} boxscores in parallel...")
                    await update_run_progress(run_id, details)
                    
                    # Check for cancellation
                    if cancellation_token:
                        cancellation_token.check()
                    
                    # Fetch all boxscores in parallel
                    loop = asyncio.get_event_loop()
                    fetch_tasks = [
                        loop.run_in_executor(None, NBAClient.get_game_by_id, game.nba_game_id)
                        for game in games_needing_update
                    ]
                    boxscores = await asyncio.gather(*fetch_tasks, return_exceptions=True)
                    
                    details["logs"].append(f"✓ Retrieved {len(boxscores)} boxscores, processing results...")
                    await update_run_progress(run_id, details)
                    
                    # Process each game with its boxscore
                    for game_idx, (game, boxscore) in enumerate(zip(games_needing_update, boxscores), 1):
                        try:
                            home_abbr = game.home_team.abbreviation if game.home_team else "???"
                            away_abbr = game.away_team.abbreviation if game.away_team else "???"
                            
                            if isinstance(boxscore, Exception):
                                error_msg = f"Error fetching boxscore: {str(boxscore)}"
                                details["errors"].append(error_msg)
                                details["logs"].append(f"   [{game_idx}/{len(games_needing_update)}] ❌ {away_abbr} @ {home_abbr}: {error_msg}")
                            elif boxscore:
                                # Check if game is actually final according to NBA API
                                nba_status = boxscore.get("game_status", "").lower()
                                is_final = "final" in nba_status
                                
                                if is_final:
                                    old_status = game.status
                                    old_score = f"{game.home_score}-{game.away_score}" if game.home_score is not None else "N/A"
                                    
                                    game.home_score = boxscore.get("home_score")
                                    game.away_score = boxscore.get("away_score")
                                    game.status = "final"
                                    game.last_api_sync = datetime.now(timezone.utc)
                                    details["games_updated"] += 1
                                    
                                    new_score = f"{game.home_score}-{game.away_score}"
                                    details["logs"].append(f"   [{game_idx}/{len(games_needing_update)}] ✅ {away_abbr} @ {home_abbr}: {old_status} → final, Score: {old_score} → {new_score}")
                                    
                                    teams_to_update.add(game.home_team_id)
                                    teams_to_update.add(game.away_team_id)
                                    final_games.append(game)  # Track this game as final
                                else:
                                    # Game is still live, skip it
                                    details["logs"].append(f"   [{game_idx}/{len(games_needing_update)}] ⏸️ {away_abbr} @ {home_abbr}: Still in progress (status: {nba_status}), skipping")
                            else:
                                details["logs"].append(f"   [{game_idx}/{len(games_needing_update)}] ⚠️ No boxscore data returned for {away_abbr} @ {home_abbr}")
                            
                        except Exception as e:
                            error_msg = f"Error processing game {game.id}: {str(e)}"
                            details["errors"].append(error_msg)
                            details["logs"].append(f"   [{game_idx}/{len(games_needing_update)}] ❌ {error_msg}")
                else:
                    details["logs"].append("✓ All games already have final scores, no updates needed")
                
                # Also add teams from games that didn't need updates (already final in DB)
                # For player stats, we'll check if they need updating individually
                for game in games_to_check:
                    if game not in games_needing_update and game.status == "final":
                        # Game is already final, add it to final_games for potential player stats update
                        final_games.append(game)
                    if game not in games_needing_update:
                        teams_to_update.add(game.home_team_id)
                        teams_to_update.add(game.away_team_id)
                
                # Commit game updates (will rollback if cancelled)
                if details["games_updated"] > 0:
                    try:
                        await db.commit()
                        details["logs"].append(f"💾 Committed {details['games_updated']} game updates to database")
                        await update_run_progress(run_id, details)
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No game updates to commit")
                    await update_run_progress(run_id, details)
                
                # Update standings for affected teams
                if teams_to_update:
                    details["logs"].append("")
                    details["logs"].append(f"📈 Updating standings for {len(teams_to_update)} teams:")
                    # Fetch standings once for all teams
                    details["logs"].append("   📡 Fetching league standings from NBA API...")
                    await update_run_progress(run_id, details)
                    # Run blocking API call in thread pool to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    standings_data = await loop.run_in_executor(
                        None, 
                        lambda: NBAClient.get_league_standings(
                            season=settings.current_season,
                            season_type="Regular Season"
                        )
                    )
                    details["logs"].append(f"   ✓ Retrieved standings for {len(standings_data)} teams")
                
                for team_idx, team_id in enumerate(teams_to_update, 1):
                    # Check for cancellation
                    if cancellation_token:
                        cancellation_token.check()
                    
                    try:
                        result = await db.execute(select(Team).where(Team.id == team_id))
                        team = result.scalar_one_or_none()
                        if not team:
                            details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ⚠️ Team ID {team_id} not found in database, skipping")
                            continue
                        
                        team_standing = next(
                            (s for s in standings_data if s["nba_team_id"] == team.nba_team_id),
                            None
                        )
                        
                        if team_standing:
                            result = await db.execute(
                                select(TeamStandings).where(
                                    TeamStandings.team_id == team_id,
                                    TeamStandings.season == settings.current_season,
                                )
                            )
                            standing = result.scalar_one_or_none()
                            
                            if standing:
                                old_record = f"{standing.wins}-{standing.losses}"
                                old_rank = standing.conference_rank
                                standing.wins = team_standing["wins"]
                                standing.losses = team_standing["losses"]
                                standing.conference_rank = team_standing["conference_rank"]
                                standing.last_api_sync = datetime.now(timezone.utc)
                                new_record = f"{standing.wins}-{standing.losses}"
                                new_rank = standing.conference_rank
                                
                                if old_record != new_record or old_rank != new_rank:
                                    details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ✅ Updated {team.abbreviation}: {old_record} → {new_record}, Rank {old_rank} → {new_rank}")
                                else:
                                    details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ✓ {team.abbreviation} standings unchanged: {new_record} (Rank: {new_rank})")
                            else:
                                standing = TeamStandings(
                                    team_id=team_id,
                                    season=settings.current_season,
                                    season_type="Regular Season",
                                    wins=team_standing["wins"],
                                    losses=team_standing["losses"],
                                    conference_rank=team_standing["conference_rank"],
                                    source="api",
                                    last_api_sync=datetime.now(timezone.utc),
                                )
                                db.add(standing)
                                details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ✅ Created {team.abbreviation} standings: {standing.wins}-{standing.losses} (Rank: {standing.conference_rank})")
                            
                            details["standings_updated"].append(team.abbreviation)
                        else:
                            details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ⚠️ No standings data found for {team.abbreviation} (NBA Team ID: {team.nba_team_id})")
                        
                    except Exception as e:
                        error_msg = f"Error updating standings for team {team_id}: {str(e)}"
                        details["errors"].append(error_msg)
                        details["logs"].append(f"   [{team_idx}/{len(teams_to_update)}] ❌ {error_msg}")
                
                # Commit standings updates (will rollback if cancelled)
                if details["standings_updated"]:
                    try:
                        await db.commit()
                        details["logs"].append(f"💾 Committed standings updates for {len(details['standings_updated'])} teams")
                        await update_run_progress(run_id, details)
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No standings updates to commit")
                    await update_run_progress(run_id, details)
                
                # Update player game stats ONLY for final games (not live games)
                if final_games:
                    details["logs"].append("")
                    details["logs"].append(f"👤 Updating player game stats for players in {len(final_games)} FINAL games:")
                    await update_run_progress(run_id, details)
                elif games_to_check and not final_games:
                    details["logs"].append("")
                    details["logs"].append("ℹ️ No final games to update player stats for (all games are still in progress)")
                    await update_run_progress(run_id, details)
                
                total_players_processed = 0
                players_with_stats = 0
                players_no_stats = 0
                
                for game_idx, game in enumerate(final_games, 1):
                    # Check for cancellation
                    if cancellation_token:
                        cancellation_token.check()
                    
                    try:
                        home_abbr = game.home_team.abbreviation if game.home_team else "???"
                        away_abbr = game.away_team.abbreviation if game.away_team else "???"
                        
                        # Get players from both teams
                        result = await db.execute(
                            select(Player).where(
                                or_(
                                    Player.team_id == game.home_team_id,
                                    Player.team_id == game.away_team_id
                                )
                            )
                        )
                        players = result.scalars().all()
                        
                        details["logs"].append(f"   [{game_idx}/{len(final_games)}] 🏀 {away_abbr} @ {home_abbr}: Fetching stats for {len(players)} players in parallel...")
                        await update_run_progress(run_id, details)
                        
                        # Check for cancellation
                        if cancellation_token:
                            cancellation_token.check()
                        
                        # Fetch all player game logs in parallel
                        loop = asyncio.get_event_loop()
                        player_fetch_tasks = [
                            loop.run_in_executor(
                                None,
                                lambda p=player: NBAClient.get_player_game_log(
                                    p.nba_player_id,
                                    season=settings.current_season,
                                    season_type="Regular Season"
                                )
                            )
                            for player in players
                        ]
                        game_logs = await asyncio.gather(*player_fetch_tasks, return_exceptions=True)
                        
                        # Process each player with their game log
                        for player_idx, (player, game_log) in enumerate(zip(players, game_logs), 1):
                            try:
                                if isinstance(game_log, Exception):
                                    error_msg = f"Error fetching game log: {str(game_log)}"
                                    details["errors"].append(error_msg)
                                    details["logs"].append(f"      [{player_idx}/{len(players)}] ❌ {player.full_name}: {error_msg}")
                                    continue
                                
                                if game_log and len(game_log) > 0:
                                    latest_game = game_log[0]
                                    
                                    # Check if this is the game we're processing
                                    if latest_game.get("nba_game_id") == game.nba_game_id:
                                        # Check if stats exist
                                        result = await db.execute(
                                            select(PlayerGameStats).where(
                                                PlayerGameStats.player_id == player.id,
                                                PlayerGameStats.game_id == game.id,
                                            )
                                        )
                                        existing = result.scalar_one_or_none()
                                        
                                        pts = latest_game.get("pts", 0)
                                        reb = latest_game.get("reb", 0)
                                        ast = latest_game.get("ast", 0)
                                        
                                        # Only update if stats don't exist OR game was just marked final
                                        # (to avoid re-fetching stats for games that are already complete)
                                        if existing and existing.last_api_sync and existing.last_api_sync > game.start_time_utc:
                                            # Stats already exist and were synced after game started, skip
                                            details["logs"].append(f"      [{player_idx}/{len(players)}] ✓ {player.full_name}: Stats already synced")
                                            players_no_stats += 1
                                            total_players_processed += 1
                                            continue
                                        
                                        if existing:
                                            existing.pts = pts
                                            existing.reb = reb
                                            existing.ast = ast
                                            existing.stl = latest_game.get("stl", 0)
                                            existing.blk = latest_game.get("blk", 0)
                                            existing.minutes = latest_game.get("minutes")
                                            existing.last_api_sync = datetime.now(timezone.utc)
                                            details["logs"].append(f"      [{player_idx}/{len(players)}] ✅ {player.full_name}: {pts} PTS, {reb} REB, {ast} AST (updated)")
                                        else:
                                            stats = PlayerGameStats(
                                                player_id=player.id,
                                                game_id=game.id,
                                                pts=pts,
                                                reb=reb,
                                                ast=ast,
                                                stl=latest_game.get("stl", 0),
                                                blk=latest_game.get("blk", 0),
                                                minutes=latest_game.get("minutes"),
                                                source="api",
                                                last_api_sync=datetime.now(timezone.utc),
                                            )
                                            db.add(stats)
                                            details["logs"].append(f"      [{player_idx}/{len(players)}] ✅ {player.full_name}: {pts} PTS, {reb} REB, {ast} AST")
                                        
                                        details["player_stats_updated"] += 1
                                        players_with_stats += 1
                                    else:
                                        # Player's latest game is not this game
                                        players_no_stats += 1
                                        if player_idx <= 3:  # Only log first few to avoid spam
                                            details["logs"].append(f"      [{player_idx}/{len(players)}] ℹ️ {player.full_name}: Latest game is not this game (skipped)")
                                else:
                                    players_no_stats += 1
                                    if player_idx <= 3:  # Only log first few to avoid spam
                                        details["logs"].append(f"      [{player_idx}/{len(players)}] ℹ️ {player.full_name}: No game log found")
                                
                                total_players_processed += 1
                                
                            except Exception as e:
                                error_msg = f"Error processing player {player.id} stats: {str(e)}"
                                details["errors"].append(error_msg)
                                details["logs"].append(f"      [{player_idx}/{len(players)}] ❌ {player.full_name}: {error_msg}")
                                continue
                        
                        # Update progress after each game's players are processed
                        await update_run_progress(run_id, details)
                        
                        if len(players) > 3:
                            details["logs"].append(f"      ... ({len(players) - 3} more players processed)")
                        
                    except Exception as e:
                        error_msg = f"Error processing game {game.id} players: {str(e)}"
                        details["errors"].append(error_msg)
                        details["logs"].append(f"   [{game_idx}/{len(games_to_check)}] ❌ {error_msg}")
                
                if games_to_check:
                    details["logs"].append("")
                    details["logs"].append(f"   📊 Player stats summary: {players_with_stats} players updated, {players_no_stats} players skipped (no stats for this game)")
                
                # Final commit (will rollback if cancelled)
                if details["player_stats_updated"] > 0:
                    try:
                        await db.commit()
                        details["logs"].append(f"💾 Committed {details['player_stats_updated']} player game stats updates")
                        await update_run_progress(run_id, details)
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No player stats updates to commit")
                    await update_run_progress(run_id, details)
                
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                details["duration_seconds"] = duration
                details["teams_updated"] = len(teams_to_update)
                
                # Final summary
                total_items = details["games_updated"] + len(details["standings_updated"]) + details["player_stats_updated"]
                details["logs"].append("")
                details["logs"].append(f"📊 SUMMARY:")
                details["logs"].append(f"   Games updated: {details['games_updated']}")
                details["logs"].append(f"   Standings updated: {len(details['standings_updated'])} teams ({', '.join(details['standings_updated'])})")
                details["logs"].append(f"   Player stats updated: {details['player_stats_updated']}")
                details["logs"].append(f"   Total items updated: {total_items}")
                details["logs"].append(f"   Duration: {duration:.2f} seconds")
                if details["errors"]:
                    details["logs"].append(f"   Errors: {len(details['errors'])}")
                
                print(f"[update_finished_games] Job completed successfully, returning results...")
                
                return {
                    "status": "success",
                    "items_updated": total_items,
                    "details": details
                }
                
            except asyncio.CancelledError as e:
                print(f"[update_finished_games] Job was cancelled: {e}")
                # Context manager will auto-rollback on exception
                raise  # Re-raise to be caught by scheduler
            except Exception as e:
                print(f"[update_finished_games] Job failed with exception: {e}")
                import traceback
                traceback.print_exc()
                # Context manager will auto-rollback on exception
                return {
                    "status": "failed",
                    "error": str(e),
                    "details": details
                }
    
    @staticmethod
    async def update_player_season_averages_batch(
        run_id: int,
        cancellation_token: Optional[Any] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """Batch update player season averages (every 3 days)."""
        start_time = datetime.now(timezone.utc)
        details = {
            "players_updated": 0,
            "players_skipped": 0,
            "errors": []
        }
        
        # Create our own database session
        async with AsyncSessionLocal() as db:
            try:
                # Check for cancellation before starting
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"] = []  # Initialize logs array
                details["logs"].append(f"🔍 Starting update_player_season_averages_batch job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                details["logs"].append(f"📦 Batch size: {batch_size}")
                
                # Get players that need updating (haven't been updated in 3 days)
                three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
                details["logs"].append(f"📅 Looking for players not updated since {three_days_ago.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                
                result = await db.execute(
                    select(PlayerSeasonStats).where(
                        or_(
                            PlayerSeasonStats.last_api_sync < three_days_ago,
                            PlayerSeasonStats.last_api_sync.is_(None)
                        ),
                        PlayerSeasonStats.season == settings.current_season,
                        PlayerSeasonStats.is_manual_override == False
                    ).limit(batch_size)
                )
                stats_to_update = result.scalars().all()
                
                details["logs"].append(f"📊 Found {len(stats_to_update)} players needing updates")
                
                if not stats_to_update:
                    details["logs"].append("✅ No players need updating. All players are up to date.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details)
                    return {
                        "status": "success",
                        "items_updated": 0,
                        "details": details
                    }
                
                details["logs"].append("")
                details["logs"].append(f"👤 Processing {len(stats_to_update)} players:")
                
                for idx, stats in enumerate(stats_to_update, 1):
                    # Check for cancellation
                    if cancellation_token:
                        cancellation_token.check()
                    
                    try:
                        result = await db.execute(
                            select(Player).where(Player.id == stats.player_id)
                        )
                        player = result.scalar_one_or_none()
                        if not player:
                            details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ⚠️ Player ID {stats.player_id} not found, skipping")
                            details["players_skipped"] += 1
                            continue
                        
                        last_sync = stats.last_api_sync.strftime('%Y-%m-%d %H:%M') if stats.last_api_sync else "Never"
                        details["logs"].append(f"   [{idx}/{len(stats_to_update)}] 📡 Fetching stats for {player.full_name} (Last sync: {last_sync})...")
                        
                        # Run blocking API call in thread pool to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        career_data = await loop.run_in_executor(None, NBAClient.get_player_career_stats, player.nba_player_id)
                        season_data = next(
                            (s for s in career_data.get("seasons", []) if s["season"] == settings.current_season),
                            None
                        )
                        
                        if season_data:
                            old_pts = stats.pts
                            old_reb = stats.reb
                            old_ast = stats.ast
                            
                            stats.pts = season_data["pts"]
                            stats.reb = season_data["reb"]
                            stats.ast = season_data["ast"]
                            stats.stl = season_data["stl"]
                            stats.blk = season_data["blk"]
                            stats.games_played = season_data["games_played"]
                            stats.minutes = season_data["minutes"]
                            stats.fg_pct = season_data.get("fg_pct")
                            stats.fg3_pct = season_data.get("fg3_pct")
                            stats.ft_pct = season_data.get("ft_pct")
                            stats.last_api_sync = datetime.now(timezone.utc)
                            details["players_updated"] += 1
                            
                            changes = []
                            if old_pts != stats.pts:
                                changes.append(f"PTS: {old_pts} → {stats.pts}")
                            if old_reb != stats.reb:
                                changes.append(f"REB: {old_reb} → {stats.reb}")
                            if old_ast != stats.ast:
                                changes.append(f"AST: {old_ast} → {stats.ast}")
                            
                            if changes:
                                details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ✅ Updated {player.full_name}: {', '.join(changes)}")
                            else:
                                details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ✓ {player.full_name}: Stats unchanged ({stats.pts} PTS, {stats.reb} REB, {stats.ast} AST)")
                        else:
                            details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ⚠️ {player.full_name}: No season data found for {settings.current_season}")
                            details["players_skipped"] += 1
                        
                        # Rate limiting
                        await asyncio.sleep(0.6)
                        
                    except Exception as e:
                        error_msg = f"Error updating player {stats.player_id}: {str(e)}"
                        details["errors"].append(error_msg)
                        details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ❌ {error_msg}")
                        continue
                
                # Commit updates (will rollback if cancelled)
                if details["players_updated"] > 0:
                    try:
                        await db.commit()
                        details["logs"].append("")
                        details["logs"].append(f"💾 Committed {details['players_updated']} player updates to database")
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("")
                    details["logs"].append("ℹ️ No player updates to commit")
                
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                details["duration_seconds"] = duration
                
                # Final summary
                details["logs"].append("")
                details["logs"].append(f"📊 SUMMARY:")
                details["logs"].append(f"   Players updated: {details['players_updated']}")
                details["logs"].append(f"   Players skipped: {details['players_skipped']}")
                details["logs"].append(f"   Total processed: {len(stats_to_update)}")
                details["logs"].append(f"   Duration: {duration:.2f} seconds")
                if details["errors"]:
                    details["logs"].append(f"   Errors: {len(details['errors'])}")
                
                return {
                    "status": "success",
                    "items_updated": details["players_updated"],
                    "details": details
                }
                
            except asyncio.CancelledError as e:
                # Context manager will auto-rollback on exception
                raise  # Re-raise to be caught by scheduler
            except Exception as e:
                # Context manager will auto-rollback on exception
                return {
                    "status": "failed",
                    "error": str(e),
                    "details": details
                }
    
    @staticmethod
    async def update_schedules(
        run_id: int,
        cancellation_token: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Check for schedule changes and update games table (every 3 days)."""
        start_time = datetime.now(timezone.utc)
        details = {
            "teams_updated": 0,
            "games_added": 0,
            "games_updated": 0,
            "errors": [],
            "logs": []
        }
        
        # Create our own database session
        async with AsyncSessionLocal() as db:
            try:
                # Check for cancellation before starting
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"].append(f"🔍 Starting update_schedules job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                details["logs"].append(f"📅 Season: {settings.current_season}")
                
                result = await db.execute(select(Team))
                teams = result.scalars().all()
                details["logs"].append(f"🏟️ Found {len(teams)} teams in database")
                details["logs"].append("")
                details["logs"].append(f"📋 Processing schedules for {len(teams)} teams:")
                
                team_abbr_map = {t.abbreviation: t.id for t in teams}
                
                for team_idx, team in enumerate(teams, 1):
                    # Check for cancellation
                    if cancellation_token:
                        cancellation_token.check()
                    
                    try:
                        details["logs"].append(f"   [{team_idx}/{len(teams)}] 📡 Fetching schedule for {team.abbreviation}...")
                        # Run blocking API call in thread pool to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        schedule = await loop.run_in_executor(
                            None,
                            lambda: NBAClient.get_team_schedule(
                                team.nba_team_id,
                                season=settings.current_season
                            )
                        )
                        details["logs"].append(f"   [{team_idx}/{len(teams)}] ✓ Retrieved {len(schedule)} games for {team.abbreviation}")
                        
                        team_games_added = 0
                        team_games_updated = 0
                        team_games_skipped = 0
                        
                        for game_data in schedule:
                            nba_game_id = game_data["nba_game_id"]
                            
                            result = await db.execute(
                                select(Game).where(Game.nba_game_id == nba_game_id)
                            )
                            existing = result.scalar_one_or_none()
                            
                            opponent_id = team_abbr_map.get(game_data["opponent_abbr"])
                            if not opponent_id:
                                team_games_skipped += 1
                                continue
                            
                            is_home = game_data["is_home"]
                            home_team_id = team.id if is_home else opponent_id
                            away_team_id = opponent_id if is_home else team.id
                            
                            from datetime import datetime as dt
                            try:
                                game_date_str = game_data["game_date"]
                                game_time_str = game_data.get("game_time", "00:00")
                                if game_time_str and game_time_str != "00:00":
                                    game_datetime = dt.strptime(f"{game_date_str} {game_time_str}", "%Y-%m-%d %H:%M")
                                else:
                                    game_datetime = dt.strptime(game_date_str, "%Y-%m-%d")
                            except (ValueError, TypeError):
                                team_games_skipped += 1
                                continue
                            
                            if existing:
                                # Update existing game
                                old_status = existing.status
                                old_score = f"{existing.home_score}-{existing.away_score}" if existing.home_score is not None else "N/A"
                                
                                existing.status = game_data.get("status", "scheduled")
                                existing.home_score = game_data.get("home_score")
                                existing.away_score = game_data.get("away_score")
                                existing.last_api_sync = datetime.now(timezone.utc)
                                details["games_updated"] += 1
                                team_games_updated += 1
                            else:
                                # Create new game
                                game = Game(
                                    nba_game_id=nba_game_id,
                                    season=settings.current_season,
                                    season_type="Regular Season",
                                    home_team_id=home_team_id,
                                    away_team_id=away_team_id,
                                    start_time_utc=game_datetime,
                                    status=game_data.get("status", "scheduled"),
                                    home_score=game_data.get("home_score"),
                                    away_score=game_data.get("away_score"),
                                    source="api",
                                    last_api_sync=datetime.now(timezone.utc),
                                )
                                db.add(game)
                                details["games_added"] += 1
                                team_games_added += 1
                        
                        if team_games_added > 0 or team_games_updated > 0:
                            details["logs"].append(f"   [{team_idx}/{len(teams)}] ✅ {team.abbreviation}: {team_games_added} added, {team_games_updated} updated, {team_games_skipped} skipped")
                        else:
                            details["logs"].append(f"   [{team_idx}/{len(teams)}] ✓ {team.abbreviation}: No changes ({team_games_skipped} skipped)")
                        
                        details["teams_updated"] += 1
                        
                    except Exception as e:
                        error_msg = f"Error updating schedule for team {team.id}: {str(e)}"
                        details["errors"].append(error_msg)
                        details["logs"].append(f"   [{team_idx}/{len(teams)}] ❌ {team.abbreviation}: {error_msg}")
                        continue
                
                # Commit updates (will rollback if cancelled)
                total_games_changed = details["games_added"] + details["games_updated"]
                if total_games_changed > 0:
                    try:
                        await db.commit()
                        details["logs"].append("")
                        details["logs"].append(f"💾 Committed {total_games_changed} game changes to database ({details['games_added']} added, {details['games_updated']} updated)")
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("")
                    details["logs"].append("ℹ️ No game changes to commit")
                
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                details["duration_seconds"] = duration
                
                # Final summary
                details["logs"].append("")
                details["logs"].append(f"📊 SUMMARY:")
                details["logs"].append(f"   Teams processed: {details['teams_updated']}/{len(teams)}")
                details["logs"].append(f"   Games added: {details['games_added']}")
                details["logs"].append(f"   Games updated: {details['games_updated']}")
                details["logs"].append(f"   Total changes: {total_games_changed}")
                details["logs"].append(f"   Duration: {duration:.2f} seconds")
                if details["errors"]:
                    details["logs"].append(f"   Errors: {len(details['errors'])}")
                
                return {
                    "status": "success",
                    "items_updated": total_games_changed,
                    "details": details
                }
                
            except asyncio.CancelledError as e:
                # Context manager will auto-rollback on exception
                raise  # Re-raise to be caught by scheduler
            except Exception as e:
                # Context manager will auto-rollback on exception
                return {
                    "status": "failed",
                    "error": str(e),
                    "details": details
                }

