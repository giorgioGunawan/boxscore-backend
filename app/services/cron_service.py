"""Cron job service for scheduled data updates."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_, text
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


async def update_run_progress(run_id: int, details: Dict[str, Any], db_session: Optional[AsyncSession] = None):
    """Update CronRun details during execution for real-time progress tracking."""
    try:
        if db_session:
            # Use the existing session (no lock issues!)
            result = await db_session.execute(select(CronRun).where(CronRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.details = details.copy()
                await db_session.flush()  # Flush but don't commit (let main transaction handle it)
        else:
            # Fallback: Use a separate session (may lock, but better than nothing)
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(CronRun).where(CronRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.details = details.copy()
                    await db.commit()
    except Exception as e:
        # Silently fail - logs are still in memory and will be saved at the end
        pass


class CronService:
    """Service for managing cron jobs and scheduled updates."""
    
    @staticmethod
    async def update_finished_games(
        run_id: int,
        cancellation_token: Optional[Any] = None,
        hours_back: int = 12,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Check for games finished in the last X hours and update:
        - Game results (scores)
        - Team standings for both teams
        - Player last game stats
        """
        start_time = datetime.now(timezone.utc)
        details = {
            "games_updated": 0,
            "standings_updated": [],
            "player_stats_updated": 0,
            "errors": [],
            "logs": []  # Add logs array for Live logs
        }
        
        # Create our own database session
        async with AsyncSessionLocal() as db:
            try:
                # Check for cancellation before starting
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"].append(f"🔍 Starting update_finished_games job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
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
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
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
                
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
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
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                # Early exit if no games found
                if not recent_games:
                    details["logs"].append(f"✅ No games found in the last {hours_back} hours. Exiting early.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
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
                    if force:
                        # Force mode: check all games regardless of status/time
                        games_to_check.append(g)
                    else:
                        # Normal mode: only check games that started 2+ hours ago or are already final
                        if g.start_time_utc <= two_hours_ago_naive or g.status == "final":
                            games_to_check.append(g)
                        elif g.start_time_utc > two_hours_ago_naive:
                            games_skipped_recent.append(g)
                        elif g.status == "final":
                            games_skipped_already_final.append(g)
                
                details["logs"].append(f"🎯 Filtering games: {'(FORCE MODE - checking all games)' if force else ''}")
                details["logs"].append(f"   • {len(games_to_check)} games to check (started 2+ hours ago or already final)")
                if not force:
                    if games_skipped_recent:
                        details["logs"].append(f"   • {len(games_skipped_recent)} games skipped (too recent, started <2 hours ago)")
                    if games_skipped_already_final:
                        details["logs"].append(f"   • {len(games_skipped_already_final)} games skipped (already final)")
                
                if not games_to_check:
                    details["logs"].append("✅ No finished games found. All recent games are still in progress.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
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
                if force:
                    # Force mode: update all games regardless of status
                    games_needing_update = games_to_check
                else:
                    # Normal mode: only update games that aren't final or don't have scores
                    games_needing_update = [g for g in games_to_check if g.status != "final" or g.home_score is None]
                
                if games_needing_update:
                    details["logs"].append(f"📡 Fetching {len(games_needing_update)} boxscores in parallel...")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                    
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
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                    
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
                
                # Add games that are already final but might need player stats
                # (NBA API sometimes doesn't have player stats immediately after game ends)
                details["logs"].append("")
                details["logs"].append(f"🔍 Checking for final games without player stats...")
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                games_needing_player_stats = 0
                for game in games_to_check:
                    if game.status == "final" and game not in final_games:
                        if force:
                            # Force mode: process all final games regardless of whether they have stats
                            final_games.append(game)
                            games_needing_player_stats += 1
                            details["logs"].append(f"   🔄 {game.away_team.abbreviation if game.away_team else '???'} @ {game.home_team.abbreviation if game.home_team else '???'}: Force updating player stats")
                        else:
                            # Normal mode: only process final games without player stats
                            result = await db.execute(
                                select(func.count(PlayerGameStats.id)).where(
                                    PlayerGameStats.game_id == game.id
                                )
                            )
                            player_stats_count = result.scalar_one()
                            
                            if player_stats_count == 0:
                                # Game is final but has no player stats, try fetching them
                                final_games.append(game)
                                games_needing_player_stats += 1
                                details["logs"].append(f"   🔄 {game.away_team.abbreviation if game.away_team else '???'} @ {game.home_team.abbreviation if game.home_team else '???'}: Already final but missing player stats, will retry")
                
                if games_needing_player_stats == 0 and not force:
                    details["logs"].append("   ✓ All final games already have player stats")
                
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                # Commit game updates (will rollback if cancelled)
                if details["games_updated"] > 0:
                    try:
                        await db.commit()
                        details["logs"].append(f"💾 Committed {details['games_updated']} game updates to database")
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No game updates to commit")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                
                # Update standings for affected teams
                if teams_to_update:
                    details["logs"].append("")
                    details["logs"].append(f"📈 Updating standings for {len(teams_to_update)} teams:")
                    # Fetch standings once for all teams
                    details["logs"].append("   📡 Fetching league standings from NBA API...")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
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
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No standings updates to commit")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                
                # Update player game stats ONLY for final games (not live games)
                if final_games:
                    details["logs"].append("")
                    details["logs"].append(f"👤 Updating player game stats for players in {len(final_games)} FINAL games:")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                elif games_to_check and not final_games:
                    details["logs"].append("")
                    details["logs"].append("ℹ️ No final games to update player stats for (all games are still in progress)")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                
                total_players_processed = 0
                
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
                        
                        if not players:
                            details["logs"].append(f"   [{game_idx}/{len(final_games)}] ⚠️ {away_abbr} @ {home_abbr}: No players found in database for these teams")
                            continue
                        
                        details["logs"].append(f"   [{game_idx}/{len(final_games)}] 🏀 {away_abbr} @ {home_abbr}: Processing {len(players)} players...")
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                        
                        # Process each player synchronously (one at a time for better logging)
                        players_updated = 0
                        players_created = 0
                        players_skipped = 0
                        
                        loop = asyncio.get_event_loop()
                        
                        for player_idx, player in enumerate(players, 1):
                            # Check for cancellation
                            if cancellation_token:
                                cancellation_token.check()
                            
                            try:
                                # Fetch this player's game log
                                game_log = await loop.run_in_executor(
                                    None,
                                    lambda: NBAClient.get_player_game_log(
                                        player.nba_player_id,
                                        season=settings.current_season,
                                        season_type="Regular Season"
                                    )
                                )
                                
                                if not game_log or len(game_log) == 0:
                                    log_msg = f"      [{player_idx}/{len(players)}] ⚠️ {player.full_name}: No game log found"
                                    details["logs"].append(log_msg)
                                    print(log_msg)  # Also print to console
                                    players_skipped += 1
                                    continue
                                
                                # Find the matching game in the player's log
                                matching_game = None
                                for log_entry in game_log:
                                    if log_entry.get("nba_game_id") == game.nba_game_id:
                                        matching_game = log_entry
                                        break
                                
                                if not matching_game:
                                    log_msg = f"      [{player_idx}/{len(players)}] ℹ️ {player.full_name}: Didn't play in this game"
                                    details["logs"].append(log_msg)
                                    print(log_msg)  # Also print to console
                                    players_skipped += 1
                                    continue
                                
                                # Check if stats already exist
                                result = await db.execute(
                                    select(PlayerGameStats).where(
                                        PlayerGameStats.player_id == player.id,
                                        PlayerGameStats.game_id == game.id,
                                    )
                                )
                                existing = result.scalar_one_or_none()
                                
                                pts = matching_game.get("pts", 0)
                                reb = matching_game.get("reb", 0)
                                ast = matching_game.get("ast", 0)
                                stl = matching_game.get("stl", 0)
                                blk = matching_game.get("blk", 0)
                                minutes = matching_game.get("minutes", "0")
                                
                                if existing:
                                    # Update existing stats
                                    existing.pts = pts
                                    existing.reb = reb
                                    existing.ast = ast
                                    existing.stl = stl
                                    existing.blk = blk
                                    existing.minutes = minutes
                                    existing.last_api_sync = datetime.now(timezone.utc)
                                    players_updated += 1
                                    log_msg = f"      [{player_idx}/{len(players)}] ✏️ {player.full_name}: {pts} PTS, {reb} REB, {ast} AST, {minutes} MIN (updated)"
                                else:
                                    # Create new stats
                                    stats = PlayerGameStats(
                                        player_id=player.id,
                                        game_id=game.id,
                                        pts=pts,
                                        reb=reb,
                                        ast=ast,
                                        stl=stl,
                                        blk=blk,
                                        minutes=minutes,
                                        source="api",
                                        last_api_sync=datetime.now(timezone.utc),
                                    )
                                    db.add(stats)
                                    players_created += 1
                                    log_msg = f"      [{player_idx}/{len(players)}] ✅ {player.full_name}: {pts} PTS, {reb} REB, {ast} AST, {minutes} MIN (created)"
                                
                                details["logs"].append(log_msg)
                                print(log_msg)  # Also print to console
                                
                                details["player_stats_updated"] += 1
                                total_players_processed += 1
                                
                                # Update progress every 2 players for better visibility
                                if player_idx % 2 == 0 or player_idx == len(players):
                                    # Use the same db session to avoid SQLite locks
                                    await update_run_progress(run_id, details, db_session=db)
                                    await db.commit()  # Commit immediately so frontend can see updates
                                
                            except Exception as e:
                                error_msg = f"Error processing player {player.full_name}: {str(e)}"
                                details["errors"].append(error_msg)
                                log_msg = f"      [{player_idx}/{len(players)}] ❌ {player.full_name}: {str(e)}"
                                details["logs"].append(log_msg)
                                print(log_msg)  # Also print to console
                                continue
                        
                        # Log summary for this game and ensure final update
                        details["logs"].append(f"      ✅ Summary: Updated {players_updated}, created {players_created}, skipped {players_skipped} players")
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()  # Commit so frontend can see the summary
                        
                    except Exception as e:
                        error_msg = f"Error processing game {game.id} players: {str(e)}"
                        details["errors"].append(error_msg)
                        details["logs"].append(f"   [{game_idx}/{len(final_games)}] ❌ {error_msg}")
                
                if final_games:
                    details["logs"].append("")
                    details["logs"].append(f"   📊 Player stats summary: Total {total_players_processed} player stats processed across {len(final_games)} games")
                
                # Final commit (will rollback if cancelled)
                if details["player_stats_updated"] > 0:
                    try:
                        await db.commit()
                        details["logs"].append(f"💾 Committed {details['player_stats_updated']} player game stats updates")
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                    except asyncio.CancelledError:
                        await db.rollback()
                        raise
                else:
                    details["logs"].append("ℹ️ No player stats updates to commit")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                
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
                
                return {
                    "status": "success",
                    "items_updated": total_items,
                    "details": details
                }
                
            except asyncio.CancelledError as e:
                # Context manager will auto-rollback on exception
                raise  # Re-raise to be caught by scheduler
            except Exception as e:
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
        batch_size: int = 50,
        force: bool = False
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
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                details["logs"].append(f"📦 Batch size: {batch_size}")
                details["logs"].append(f"🔄 Force mode: {'ON' if force else 'OFF'}")
                details["logs"].append(f"📅 Season: {settings.current_season}")
                
                # Get players that need updating (haven't been updated in 3 days)
                if force:
                    details["logs"].append(f"📅 FORCE MODE: Updating all players regardless of last sync time")
                    result = await db.execute(
                        select(PlayerSeasonStats).where(
                            PlayerSeasonStats.season == settings.current_season,
                            PlayerSeasonStats.is_manual_override == False
                        ).limit(batch_size)
                    )
                else:
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
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                # Get total player count for context
                total_players_result = await db.execute(select(func.count(Player.id)))
                total_players = total_players_result.scalar()
                details["logs"].append(f"📊 Total players in database: {total_players}")
                
                if not stats_to_update:
                    details["logs"].append("✅ No players need updating. All players are up to date.")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    details["logs"].append(f"   Duration: {duration:.2f} seconds")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
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
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                        
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
                            old_stl = stats.stl
                            old_blk = stats.blk
                            old_gp = stats.games_played
                            
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
                                changes.append(f"PTS: {old_pts:.1f} → {stats.pts:.1f}")
                            if old_reb != stats.reb:
                                changes.append(f"REB: {old_reb:.1f} → {stats.reb:.1f}")
                            if old_ast != stats.ast:
                                changes.append(f"AST: {old_ast:.1f} → {stats.ast:.1f}")
                            if old_stl != stats.stl:
                                changes.append(f"STL: {old_stl:.1f} → {stats.stl:.1f}")
                            if old_blk != stats.blk:
                                changes.append(f"BLK: {old_blk:.1f} → {stats.blk:.1f}")
                            if old_gp != stats.games_played:
                                changes.append(f"GP: {old_gp} → {stats.games_played}")
                            
                            if changes:
                                details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ✅ Updated {player.full_name}: {', '.join(changes)}")
                            else:
                                details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ✓ {player.full_name}: Stats unchanged ({stats.pts:.1f} PTS, {stats.reb:.1f} REB, {stats.ast:.1f} AST, {stats.games_played} GP)")
                        else:
                            details["logs"].append(f"   [{idx}/{len(stats_to_update)}] ⚠️ {player.full_name}: No season data found for {settings.current_season}")
                            details["players_skipped"] += 1
                        
                        # Commit every 5 players to show progress
                        if idx % 5 == 0 and details["players_updated"] > 0:
                            await db.commit()
                            await update_run_progress(run_id, details, db_session=db)
                        
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
        cancellation_token: Optional[Any] = None,
        force: bool = False
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
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                details["logs"].append(f"📅 Season: {settings.current_season}")
                details["logs"].append(f"🔄 Force mode: {'ON' if force else 'OFF'}")
                
                result = await db.execute(select(Team))
                teams = result.scalars().all()
                details["logs"].append(f"🏟️ Found {len(teams)} teams in database")
                
                # Get current game count
                games_count_result = await db.execute(select(func.count(Game.id)))
                current_game_count = games_count_result.scalar()
                details["logs"].append(f"📊 Current games in database: {current_game_count}")
                
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
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
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                        
                        team_games_added = 0
                        team_games_updated = 0
                        team_games_skipped = 0
                        team_games_errors = 0
                        
                        details["logs"].append(f"   [{team_idx}/{len(teams)}] 🔍 Processing {len(schedule)} games for {team.abbreviation}...")
                        
                        for game_idx, game_data in enumerate(schedule, 1):
                            nba_game_id = game_data["nba_game_id"]
                            
                            result = await db.execute(
                                select(Game).where(Game.nba_game_id == nba_game_id)
                            )
                            existing = result.scalar_one_or_none()
                            
                            opponent_id = team_abbr_map.get(game_data["opponent_abbr"])
                            if not opponent_id:
                                team_games_skipped += 1
                                if game_idx <= 3 or game_idx == len(schedule):  # Log first 3 and last
                                    details["logs"].append(f"      [{game_idx}/{len(schedule)}] ⚠️ Skipping game {nba_game_id}: Opponent '{game_data['opponent_abbr']}' not found")
                                continue
                            
                            is_home = game_data["is_home"]
                            home_team_id = team.id if is_home else opponent_id
                            away_team_id = opponent_id if is_home else team.id
                            
                            # Parse game datetime - use gameDateTimeUTC from API (same logic as refresh_team_schedule)
                            try:
                                # If we have the full UTC datetime string from API, use it directly
                                if game_data.get("game_datetime_utc"):
                                    # Parse ISO format: "2025-12-09T00:00:00Z"
                                    game_datetime_str = game_data["game_datetime_utc"]
                                    if game_datetime_str.endswith('Z'):
                                        game_datetime_str = game_datetime_str[:-1] + '+00:00'
                                    game_datetime = datetime.fromisoformat(game_datetime_str).replace(tzinfo=None)  # Store as naive UTC
                                else:
                                    # Fallback: parse date/time separately (shouldn't happen with new API format)
                                    game_date_str = game_data["game_date"]
                                    game_time_str = game_data.get("game_time", "00:00")
                                    
                                    if game_time_str and game_time_str != "00:00":
                                        # Parse as UTC (gameTimeEst with Z is UTC, not Eastern)
                                        game_datetime = datetime.strptime(f"{game_date_str} {game_time_str}", "%Y-%m-%d %H:%M")
                                        # No timezone conversion needed - already UTC
                                    else:
                                        game_datetime = datetime.strptime(game_date_str, "%Y-%m-%d")
                            except (ValueError, TypeError) as e:
                                details["logs"].append(f"      [{game_idx}/{len(schedule)}] ⚠️ Error parsing datetime for game {nba_game_id}: {e}")
                                team_games_skipped += 1
                                team_games_errors += 1
                                continue
                            
                            if existing:
                                # Update existing game
                                old_status = existing.status
                                old_score = f"{existing.home_score}-{existing.away_score}" if existing.home_score is not None else "N/A"
                                old_time = existing.start_time_utc.strftime('%Y-%m-%d %H:%M:%S') if existing.start_time_utc else "None"
                                new_time = game_datetime.strftime('%Y-%m-%d %H:%M:%S')
                                
                                time_changed = existing.start_time_utc != game_datetime
                                status_changed = existing.status != game_data.get("status", "scheduled")
                                score_changed = (existing.home_score != game_data.get("home_score") or 
                                               existing.away_score != game_data.get("away_score"))
                                
                                existing.status = game_data.get("status", "scheduled")
                                existing.start_time_utc = game_datetime  # Update time with correct UTC from API
                                existing.home_score = game_data.get("home_score")
                                existing.away_score = game_data.get("away_score")
                                existing.last_api_sync = datetime.now(timezone.utc)
                                details["games_updated"] += 1
                                team_games_updated += 1
                                
                                # Log changes
                                changes = []
                                if time_changed:
                                    changes.append(f"Time: {old_time} → {new_time}")
                                if status_changed:
                                    changes.append(f"Status: {old_status} → {existing.status}")
                                if score_changed:
                                    new_score = f"{existing.home_score}-{existing.away_score}" if existing.home_score is not None else "N/A"
                                    changes.append(f"Score: {old_score} → {new_score}")
                                
                                if changes and (game_idx <= 5 or game_idx % 20 == 0):  # Log first 5 and every 20th
                                    details["logs"].append(f"      [{game_idx}/{len(schedule)}] 🔄 Updated game {nba_game_id}: {', '.join(changes)}")
                            else:
                                # Create new game
                                game = Game(
                                    nba_game_id=nba_game_id,
                                    season=settings.current_season,
                                    season_type="Regular Season",
                                    home_team_id=home_team_id,
                                    away_team_id=away_team_id,
                                    start_time_utc=game_datetime,  # Use correct UTC datetime
                                    status=game_data.get("status", "scheduled"),
                                    home_score=game_data.get("home_score"),
                                    away_score=game_data.get("away_score"),
                                    source="api",
                                    last_api_sync=datetime.now(timezone.utc),
                                )
                                db.add(game)
                                details["games_added"] += 1
                                team_games_added += 1
                                
                                # Log new games (first 5 and every 10th)
                                if game_idx <= 5 or game_idx % 10 == 0:
                                    game_time_str = game_datetime.strftime('%Y-%m-%d %H:%M:%S')
                                    home_abbr = team.abbreviation if game_data["is_home"] else game_data["opponent_abbr"]
                                    away_abbr = game_data["opponent_abbr"] if game_data["is_home"] else team.abbreviation
                                    details["logs"].append(f"      [{game_idx}/{len(schedule)}] ➕ Added game {nba_game_id}: {away_abbr} @ {home_abbr} ({game_time_str} UTC)")
                            
                            # Commit every 10 games to show progress
                            if (game_idx % 10 == 0) and (team_games_added > 0 or team_games_updated > 0):
                                await db.commit()
                                await update_run_progress(run_id, details, db_session=db)
                        
                        # Final commit for this team
                        if team_games_added > 0 or team_games_updated > 0:
                            await db.commit()
                            await update_run_progress(run_id, details, db_session=db)
                        
                        if team_games_added > 0 or team_games_updated > 0:
                            details["logs"].append(f"   [{team_idx}/{len(teams)}] ✅ {team.abbreviation}: {team_games_added} added, {team_games_updated} updated, {team_games_skipped} skipped")
                        else:
                            details["logs"].append(f"   [{team_idx}/{len(teams)}] ✓ {team.abbreviation}: No changes ({team_games_skipped} skipped)")
                        
                        if team_games_errors > 0:
                            details["logs"].append(f"   [{team_idx}/{len(teams)}] ⚠️ {team.abbreviation}: {team_games_errors} errors encountered")
                        
                        details["teams_updated"] += 1
                        await update_run_progress(run_id, details, db_session=db)
                        await db.commit()
                        
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

    @staticmethod
    async def update_players_team(
        run_id: int,
        cancellation_token: Optional[Any] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Update all players' team assignments from NBA API.
        Useful during transfer windows when players change teams.
        """
        start_time = datetime.now(timezone.utc)
        details = {
            "players_updated": 0,
            "players_unchanged": 0,
            "players_errors": 0,
            "errors": [],
            "logs": []
        }
        
        # Create our own database session
        async with AsyncSessionLocal() as db:
            try:
                # Check for cancellation before starting
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"].append(f"🔍 Starting update_players_team job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                # Get all players from database
                result = await db.execute(select(Player))
                all_players = result.scalars().all()
                
                details["logs"].append(f"📊 Found {len(all_players)} players in database")
                details["logs"].append(f"📦 Processing in batches of {batch_size}")
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                if not all_players:
                    details["logs"].append("⚠️ No players found in database")
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    details["duration_seconds"] = duration
                    return {
                        "status": "success",
                        "items_updated": 0,
                        "details": details
                    }
                
                details["logs"].append("")
                details["logs"].append(f"👤 Processing {len(all_players)} players:")
                
                # Process players in batches
                total_batches = (len(all_players) + batch_size - 1) // batch_size
                
                for batch_idx in range(0, len(all_players), batch_size):
                    batch_players = all_players[batch_idx:batch_idx + batch_size]
                    current_batch = (batch_idx // batch_size) + 1
                    
                    details["logs"].append("")
                    details["logs"].append(f"📦 Batch {current_batch}/{total_batches} ({len(batch_players)} players):")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                    
                    for idx, player in enumerate(batch_players, 1):
                        # Check for cancellation
                        if cancellation_token:
                            cancellation_token.check()
                        
                        try:
                            global_idx = batch_idx + idx
                            
                            # Fetch player info from NBA API
                            loop = asyncio.get_event_loop()
                            player_info = await loop.run_in_executor(
                                None, 
                                NBAClient.get_player_info, 
                                player.nba_player_id
                            )
                            
                            if not player_info:
                                details["logs"].append(f"   [{global_idx}/{len(all_players)}] ⚠️ {player.full_name}: No info from NBA API")
                                details["players_errors"] += 1
                                continue
                            
                            # Get the team ID from NBA API
                            nba_team_id = player_info.get("team_id")
                            
                            if not nba_team_id:
                                # Player might be a free agent or retired
                                if player.team_id is not None:
                                    # Player was on a team, now is not
                                    old_team_result = await db.execute(
                                        select(Team).where(Team.id == player.team_id)
                                    )
                                    old_team = old_team_result.scalar_one_or_none()
                                    old_team_abbr = old_team.abbreviation if old_team else "???"
                                    
                                    player.team_id = None
                                    player.last_api_sync = datetime.now(timezone.utc)
                                    details["players_updated"] += 1
                                    details["logs"].append(f"   [{global_idx}/{len(all_players)}] 🔄 {player.full_name}: {old_team_abbr} → Free Agent")
                                else:
                                    details["logs"].append(f"   [{global_idx}/{len(all_players)}] ✓ {player.full_name}: Free Agent (unchanged)")
                                    details["players_unchanged"] += 1
                                continue
                            
                            # Find the team in our database
                            team_result = await db.execute(
                                select(Team).where(Team.nba_team_id == nba_team_id)
                            )
                            team = team_result.scalar_one_or_none()
                            
                            if not team:
                                details["logs"].append(f"   [{global_idx}/{len(all_players)}] ⚠️ {player.full_name}: Team {nba_team_id} not found in database")
                                details["players_errors"] += 1
                                continue
                            
                            # Check if team has changed
                            if player.team_id != team.id:
                                # Team changed!
                                old_team_result = await db.execute(
                                    select(Team).where(Team.id == player.team_id)
                                )
                                old_team = old_team_result.scalar_one_or_none()
                                old_team_abbr = old_team.abbreviation if old_team else "Free Agent"
                                
                                player.team_id = team.id
                                player.last_api_sync = datetime.now(timezone.utc)
                                details["players_updated"] += 1
                                details["logs"].append(f"   [{global_idx}/{len(all_players)}] ✅ {player.full_name}: {old_team_abbr} → {team.abbreviation}")
                            else:
                                # Team unchanged
                                player.last_api_sync = datetime.now(timezone.utc)
                                details["players_unchanged"] += 1
                                # Only log every 10th unchanged player to reduce noise
                                if details["players_unchanged"] % 10 == 0:
                                    details["logs"].append(f"   [{global_idx}/{len(all_players)}] ✓ {player.full_name}: {team.abbreviation} (unchanged)")
                            
                            # Update progress every 5 players
                            if idx % 5 == 0 or idx == len(batch_players):
                                await update_run_progress(run_id, details, db_session=db)
                                await db.commit()
                            
                        except Exception as e:
                            error_msg = f"Error processing player {player.full_name}: {str(e)}"
                            details["errors"].append(error_msg)
                            details["logs"].append(f"   [{global_idx}/{len(all_players)}] ❌ {player.full_name}: {str(e)}")
                            details["players_errors"] += 1
                            continue
                    
                    # Commit after each batch
                    await db.commit()
                    details["logs"].append(f"   💾 Batch {current_batch} committed")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                details["duration_seconds"] = duration
                
                # Final summary
                details["logs"].append("")
                details["logs"].append(f"📊 SUMMARY:")
                details["logs"].append(f"   Total players: {len(all_players)}")
                details["logs"].append(f"   Players with team changes: {details['players_updated']}")
                details["logs"].append(f"   Players unchanged: {details['players_unchanged']}")
                details["logs"].append(f"   Errors: {details['players_errors']}")
                details["logs"].append(f"   Duration: {duration:.2f} seconds")
                
                return {
                    "status": "success",
                    "items_updated": details["players_updated"],
                    "details": details
                }
                
            except asyncio.CancelledError as e:
                # Context manager will auto-rollback on exception
                raise  # Re-raise to be caught by scheduler
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Context manager will auto-rollback on exception
                return {
                    "status": "failed",
                    "error": str(e),
                    "details": details
                }

    @staticmethod
    async def update_team_results(
        run_id: int,
        cancellation_token: Optional[Any] = None,
        team_id: Optional[int] = None,
        limit: Optional[int] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Comprehensive update of game results for teams.
        """
        start_time = datetime.now(timezone.utc)
        details = {
            "games_updated": 0,
            "teams_processed": 0,
            "errors": [],
            "logs": []
        }
        
        # Handle "all games" (if limit is 0 or -1)
        if limit is not None and limit <= 0:
            limit = None
            
        async with AsyncSessionLocal() as db:
            try:
                if cancellation_token:
                    cancellation_token.check()
                
                details["logs"].append(f"🔍 Starting update_team_results job at {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                
                # Fetch all teams once for mapping
                result = await db.execute(select(Team))
                all_teams = result.scalars().all()
                # Use int for nba_team_id matching
                team_nba_map = {int(t.nba_team_id): t for t in all_teams}
                
                # OPTIMIZATION: If all teams and all (or many) games, use a single league-wide call
                if not team_id:
                    details["logs"].append("📡 Fetching league-wide game log (all teams)...")
                    await update_run_progress(run_id, details, db_session=db)
                    await db.commit()
                    
                    try:
                        loop = asyncio.get_event_loop()
                        from nba_api.stats.endpoints import leaguegamefinder
                        
                        def fetch_league():
                            finder = leaguegamefinder.LeagueGameFinder(
                                season_nullable=settings.current_season,
                                league_id_nullable="00", # NBA
                                season_type_nullable="Regular Season"
                            )
                            return finder.get_data_frames()[0]
                            
                        api_games_df = await loop.run_in_executor(None, fetch_league)
                        
                        # Process games from dataframe
                        game_updates = 0
                        
                        # Sort by date DESC
                        api_games_df = api_games_df.sort_values("GAME_DATE", ascending=False)
                        
                        # Filter to only processed NBA games (GAME_ID starts with 002)
                        nba_games_only = api_games_df[api_games_df["GAME_ID"].str.startswith("002")]
                        
                        details["logs"].append(f"   ✓ Found {len(nba_games_only)} team-game rows in API log")
                        
                        processed_team_counts = {}
                        
                        for _, row in nba_games_only.iterrows():
                            nba_id = row["GAME_ID"]
                            nba_team_id = int(row["TEAM_ID"])
                            
                            # Skip if we reach limit for THIS team
                            if limit:
                                processed_team_counts[nba_team_id] = processed_team_counts.get(nba_team_id, 0) + 1
                                if processed_team_counts[nba_team_id] > limit:
                                    continue
                            
                            # Find game in DB
                            result = await db.execute(
                                select(Game).where(Game.nba_game_id == nba_id)
                            )
                            game = result.scalar_one_or_none()
                            
                            if not game:
                                continue
                            
                            changed = False
                            pts = row.get("PTS")
                            
                            current_team = team_nba_map.get(nba_team_id)
                            if not current_team:
                                continue
                                
                            if game.home_team_id == current_team.id:
                                if game.home_score != pts:
                                    game.home_score = pts
                                    changed = True
                            elif game.away_team_id == current_team.id:
                                if game.away_score != pts:
                                    game.away_score = pts
                                    changed = True
                                    
                            if row.get("WL") and game.status != "final":
                                game.status = "final"
                                changed = True
                                
                            if changed:
                                game.last_api_sync = datetime.now(timezone.utc)
                                game_updates += 1
                                details["games_updated"] += 1
                        
                        details["logs"].append(f"   ✅ Updated {game_updates} game scores/statuses via league-wide sync")
                        details["teams_processed"] = len(all_teams)
                        
                    except Exception as e:
                        details["logs"].append(f"   ❌ League-wide sync failed: {str(e)}")
                        raise e
                else:
                    # Specific team sync
                    team = next((t for t in all_teams if t.id == team_id), None)
                    if not team:
                        raise Exception(f"Team ID {team_id} not found")
                        
                    details["logs"].append(f"📡 Processing single team: {team.abbreviation}...")
                    
                    loop = asyncio.get_event_loop()
                    api_games = await loop.run_in_executor(
                        None,
                        lambda: NBAClient.get_team_games(
                            team.nba_team_id,
                            season=settings.current_season
                        )
                    )
                    
                    if limit:
                        api_games = api_games[:limit]
                        
                    details["logs"].append(f"   ✓ Found {len(api_games)} games for {team.abbreviation}")
                    
                    team_updates = 0
                    for api_game in api_games:
                        nba_id = api_game["nba_game_id"]
                        result = await db.execute(
                            select(Game).where(Game.nba_game_id == nba_id)
                        )
                        game = result.scalar_one_or_none()
                        
                        if not game:
                            continue
                            
                        changed = False
                        pts = api_game["team_score"]
                        
                        if api_game["is_home"]:
                            if game.home_score != pts:
                                game.home_score = pts
                                changed = True
                        else:
                            if game.away_score != pts:
                                game.away_score = pts
                                changed = True
                                
                        if api_game["win_loss"] and game.status != "final":
                            game.status = "final"
                            changed = True
                            
                        if changed:
                            game.last_api_sync = datetime.now(timezone.utc)
                            team_updates += 1
                            details["games_updated"] += 1
                            
                    details["logs"].append(f"   ✅ Updated {team_updates} games for {team.abbreviation}")
                    details["teams_processed"] = 1
                
                await db.commit()
                
                # Update standings
                details["logs"].append("")
                details["logs"].append(f"📈 Updating standings for all teams...")
                await update_run_progress(run_id, details, db_session=db)
                await db.commit()
                
                count = await StandingsService.refresh_all_standings(
                    db,
                    season=settings.current_season,
                    season_type="Regular Season"
                )
                details["logs"].append(f"   ✓ Updated standings for {count} teams")
                await db.commit()

                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                details["duration_seconds"] = duration
                
                details["logs"].append("")
                details["logs"].append("📊 SUMMARY:")
                details["logs"].append(f"   Teams processed: {details['teams_processed']}")
                details["logs"].append(f"   Total games updated: {details['games_updated']}")
                details["logs"].append(f"   Duration: {duration:.2f} seconds")
                
                return {
                    "status": "success",
                    "items_updated": details["games_updated"],
                    "details": details
                }
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {
                    "status": "failed",
                    "error": str(e),
                    "details": details
                }
