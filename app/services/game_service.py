"""Game service with cache-aside pattern."""
import asyncio
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Game, Team
from app.nba_client import NBAClient
from app.cache import cache_get, cache_set, cache_delete_pattern
from app.config import get_settings
from app.services.team_service import TeamService

settings = get_settings()


class GameService:
    """Service for game-related operations."""
    
    @staticmethod
    async def get_next_games(
        db: AsyncSession,
        team_id: int,
        count: int = 5,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> list[dict]:
        """
        Get next N upcoming games for a team.
        Uses the schedule endpoint which includes future games.
        """
        season = season or settings.current_season
        cache_key = f"team:{team_id}:next_games:{count}:{season}:{season_type}"
        
        # Check cache first
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # Get team
        result = await db.execute(select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        
        if not team:
            return []
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Query upcoming games from DB
        result = await db.execute(
            select(Game)
            .options(selectinload(Game.home_team), selectinload(Game.away_team))
            .where(
                or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
                Game.season == season,
                Game.status == "scheduled",
            )
            .order_by(Game.start_time_utc.asc())
            .limit(count)
        )
        games = result.scalars().all()
        
        # If not enough games in DB or forcing refresh, fetch from schedule API
        if len(games) < count or force_refresh:
            try:
                await GameService.refresh_team_schedule(db, team, season)
                
                # Re-query
                result = await db.execute(
                    select(Game)
                    .options(selectinload(Game.home_team), selectinload(Game.away_team))
                    .where(
                        or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
                        Game.season == season,
                        Game.status == "scheduled",
                    )
                    .order_by(Game.start_time_utc.asc())
                    .limit(count)
                )
                games = result.scalars().all()
            except Exception as e:
                print(f"Error refreshing schedule for team {team_id}: {e}")
                # Continue with whatever games we have in DB
        
        response = []
        # Convert UTC back to Eastern Time for display
        eastern = zoneinfo.ZoneInfo("America/New_York")
        
        for game in games:
            is_home = game.home_team_id == team_id
            opponent = game.away_team if is_home else game.home_team
            
            # Convert UTC to Eastern Time
            if game.start_time_utc:
                # Make UTC timezone-aware, convert to Eastern, then format
                utc_time = game.start_time_utc.replace(tzinfo=timezone.utc)
                eastern_time = utc_time.astimezone(eastern)
                game_date = eastern_time.strftime("%Y-%m-%d")
                game_time = eastern_time.strftime("%H:%M")
            else:
                game_date = None
                game_time = None
            
            response.append({
                "game_id": game.id,
                "nba_game_id": game.nba_game_id,
                "date": game_date,
                "time": game_time,
                "opponent": opponent.abbreviation if opponent else "TBD",
                "opponent_name": opponent.name if opponent else "TBD",
                "is_home": is_home,
                "venue": "Home" if is_home else "Away",
            })
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_games)
        
        return response
    
    @staticmethod
    async def get_last_games(
        db: AsyncSession,
        team_id: int,
        count: int = 5,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> list[dict]:
        """
        Get last N completed games for a team.
        """
        season = season or settings.current_season
        cache_key = f"team:{team_id}:last_games:{count}:{season}:{season_type}"
        
        # Check cache first
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # Get team
        result = await db.execute(select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        
        if not team:
            return []
        
        now = datetime.utcnow()
        
        # Query past games from DB
        result = await db.execute(
            select(Game)
            .options(selectinload(Game.home_team), selectinload(Game.away_team))
            .where(
                or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
                Game.season == season,
                Game.status == "final",
            )
            .order_by(Game.start_time_utc.desc())
            .limit(count)
        )
        games = result.scalars().all()
        
        # If not enough games in DB or forcing refresh, fetch from NBA API
        if len(games) < count or force_refresh:
            try:
                await GameService.refresh_team_games(db, team, season, season_type)
                
                # Re-query
                result = await db.execute(
                    select(Game)
                    .options(selectinload(Game.home_team), selectinload(Game.away_team))
                    .where(
                        or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
                        Game.season == season,
                        Game.status == "final",
                    )
                    .order_by(Game.start_time_utc.desc())
                    .limit(count)
                )
                games = result.scalars().all()
            except Exception as e:
                print(f"Error refreshing games for team {team_id}: {e}")
                # Continue with whatever games we have in DB
        
        response = []
        # Convert UTC back to Eastern Time for display
        eastern = zoneinfo.ZoneInfo("America/New_York")
        
        for game in games:
            is_home = game.home_team_id == team_id
            opponent = game.away_team if is_home else game.home_team
            team_score = game.home_score if is_home else game.away_score
            opponent_score = game.away_score if is_home else game.home_score
            
            result_str = None
            if team_score is not None and opponent_score is not None:
                result_str = "W" if team_score > opponent_score else "L"
            
            # Convert UTC to Eastern Time
            if game.start_time_utc:
                utc_time = game.start_time_utc.replace(tzinfo=timezone.utc)
                eastern_time = utc_time.astimezone(eastern)
                game_date = eastern_time.strftime("%Y-%m-%d")
            else:
                game_date = None
            
            response.append({
                "game_id": game.id,
                "nba_game_id": game.nba_game_id,
                "date": game_date,
                "opponent": opponent.abbreviation if opponent else "???",
                "opponent_name": opponent.name if opponent else "???",
                "is_home": is_home,
                "team_score": team_score,
                "opponent_score": opponent_score,
                "result": result_str,
                "score_display": f"{team_score}-{opponent_score}" if team_score is not None else None,
            })
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_games)
        
        return response
    
    @staticmethod
    async def refresh_team_games(
        db: AsyncSession,
        team: Team,
        season: str,
        season_type: str
    ) -> int:
        """
        Refresh games for a team from NBA API.
        Returns number of games added/updated.
        """
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        games_data = await loop.run_in_executor(
            None,
            lambda: NBAClient.get_team_games(
                team.nba_team_id,
                season=season,
                season_type=season_type,
            )
        )
        
        # Get team ID mappings
        team_abbr_map = await TeamService.get_team_abbr_map(db)
        team_id_map = await TeamService.get_team_id_map(db)
        
        # Build a map of game_id -> team scores for merging
        # We need to fetch opponent data to get complete scores
        game_scores: dict[str, dict] = {}
        
        count = 0
        for game_data in games_data:
            nba_game_id = game_data["nba_game_id"]
            is_home = game_data["is_home"]
            team_score = game_data.get("team_score")
            
            # Store this team's score
            if nba_game_id not in game_scores:
                game_scores[nba_game_id] = {"home_score": None, "away_score": None}
            
            if team_score is not None:
                if is_home:
                    game_scores[nba_game_id]["home_score"] = team_score
                else:
                    game_scores[nba_game_id]["away_score"] = team_score
            
            # Check if game exists
            result = await db.execute(
                select(Game).where(Game.nba_game_id == nba_game_id)
            )
            game = result.scalar_one_or_none()
            
            # Determine home/away teams
            opponent_id = team_abbr_map.get(game_data["opponent_abbr"])
            
            if not opponent_id:
                continue  # Skip if opponent not found
            
            home_team_id = team.id if is_home else opponent_id
            away_team_id = opponent_id if is_home else team.id
            
            # Parse game date - NBA API returns dates in Eastern Time
            try:
                from datetime import timezone
                import zoneinfo
                
                # Parse date (no time component, assume midnight Eastern)
                eastern = zoneinfo.ZoneInfo("America/New_York")
                game_date_et = datetime.strptime(game_data["game_date"], "%Y-%m-%d")
                game_date_et = game_date_et.replace(tzinfo=eastern)
                game_date = game_date_et.astimezone(timezone.utc).replace(tzinfo=None)  # Store as naive UTC
            except (ValueError, TypeError):
                continue
            
            # Determine status
            is_completed = team_score is not None and game_data.get("win_loss") is not None
            status = "final" if is_completed else "scheduled"
            
            if game:
                # Update existing game
                game.status = status
                # Update scores - merge with existing
                if is_home and team_score is not None:
                    game.home_score = team_score
                elif not is_home and team_score is not None:
                    game.away_score = team_score
            else:
                # Create new game
                home_score = team_score if is_home else None
                away_score = team_score if not is_home else None
                
                game = Game(
                    nba_game_id=nba_game_id,
                    season=season,
                    season_type=season_type,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    start_time_utc=game_date,
                    status=status,
                    home_score=home_score,
                    away_score=away_score,
                )
                db.add(game)
                count += 1
        
        await db.commit()
        
        # Now fetch complete scores for games missing opponent scores
        # Get all games that have only one score
        result = await db.execute(
            select(Game).where(
                or_(Game.home_team_id == team.id, Game.away_team_id == team.id),
                Game.season == season,
                Game.status == "final",
                or_(Game.home_score == None, Game.away_score == None),
            )
        )
        incomplete_games = result.scalars().all()
        
        # For each incomplete game, fetch the boxscore to get both scores
        for game in incomplete_games:
            try:
                # Run in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                game_data = await loop.run_in_executor(None, NBAClient.get_game_by_id, game.nba_game_id)
                if game_data:
                    if game_data.get("home_score") is not None:
                        game.home_score = game_data["home_score"]
                    if game_data.get("away_score") is not None:
                        game.away_score = game_data["away_score"]
            except Exception as e:
                print(f"Error fetching game {game.nba_game_id}: {e}")
                continue
        
        await db.commit()
        
        # Invalidate cache for this team
        await cache_delete_pattern(f"team:{team.id}:*")
        
        return count
    
    @staticmethod
    async def refresh_team_schedule(
        db: AsyncSession,
        team: Team,
        season: str
    ) -> int:
        """
        Refresh full season schedule for a team from NBA API.
        This includes future games, not just played games.
        """
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        schedule_data = await loop.run_in_executor(
            None,
            lambda: NBAClient.get_team_schedule(
                team.nba_team_id,
                season=season,
            )
        )
        
        # Get team ID mappings
        team_abbr_map = await TeamService.get_team_abbr_map(db)
        
        count = 0
        for game_data in schedule_data:
            nba_game_id = game_data["nba_game_id"]
            
            # Check if game exists
            result = await db.execute(
                select(Game).where(Game.nba_game_id == nba_game_id)
            )
            game = result.scalar_one_or_none()
            
            # Get opponent team ID
            opponent_id = team_abbr_map.get(game_data["opponent_abbr"])
            if not opponent_id:
                continue
            
            is_home = game_data["is_home"]
            home_team_id = team.id if is_home else opponent_id
            away_team_id = opponent_id if is_home else team.id
            
            # Parse game date and time - NBA API returns times in Eastern Time
            try:
                from datetime import timezone
                import zoneinfo
                
                game_date_str = game_data["game_date"]
                game_time_str = game_data.get("game_time", "00:00")
                
                # Parse as Eastern Time
                eastern = zoneinfo.ZoneInfo("America/New_York")
                if game_time_str and game_time_str != "00:00":
                    game_datetime_et = datetime.strptime(f"{game_date_str} {game_time_str}", "%Y-%m-%d %H:%M")
                else:
                    game_datetime_et = datetime.strptime(game_date_str, "%Y-%m-%d")
                
                # Make it timezone-aware (Eastern) then convert to UTC
                game_datetime_et = game_datetime_et.replace(tzinfo=eastern)
                game_datetime = game_datetime_et.astimezone(timezone.utc).replace(tzinfo=None)  # Store as naive UTC
            except (ValueError, TypeError):
                continue
            
            status = game_data.get("status", "scheduled")
            home_score = game_data.get("home_score")
            away_score = game_data.get("away_score")
            
            # Convert scores to int if they exist
            if home_score is not None:
                try:
                    home_score = int(home_score)
                except (ValueError, TypeError):
                    home_score = None
            if away_score is not None:
                try:
                    away_score = int(away_score)
                except (ValueError, TypeError):
                    away_score = None
            
            if game:
                # Update existing game
                game.status = status
                if home_score is not None:
                    game.home_score = home_score
                if away_score is not None:
                    game.away_score = away_score
            else:
                # Create new game
                game = Game(
                    nba_game_id=nba_game_id,
                    season=season,
                    season_type="Regular Season",
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    start_time_utc=game_datetime,
                    status=status,
                    home_score=home_score,
                    away_score=away_score,
                )
                db.add(game)
                count += 1
        
        await db.commit()
        
        # Invalidate cache for this team
        await cache_delete_pattern(f"team:{team.id}:*")
        
        return count
    
    @staticmethod
    async def get_or_create_game_from_log(
        db: AsyncSession,
        game_log: dict,
        team_id: int,
        season: str,
        season_type: str
    ) -> Optional[Game]:
        """
        Get or create a game from a player/team game log entry.
        """
        nba_game_id = game_log.get("nba_game_id")
        if not nba_game_id:
            return None
        
        # Check if game exists
        result = await db.execute(
            select(Game).where(Game.nba_game_id == nba_game_id)
        )
        game = result.scalar_one_or_none()
        
        if game:
            return game
        
        # Get team info
        result = await db.execute(select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        
        if not team:
            return None
        
        # Get opponent
        team_abbr_map = await TeamService.get_team_abbr_map(db)
        opponent_id = team_abbr_map.get(game_log.get("opponent_abbr", ""))
        
        if not opponent_id:
            return None
        
        is_home = game_log.get("is_home", False)
        home_team_id = team_id if is_home else opponent_id
        away_team_id = opponent_id if is_home else team_id
        
        # Parse game date - NBA API returns dates in Eastern Time  
        try:
            from datetime import timezone
            import zoneinfo
            
            eastern = zoneinfo.ZoneInfo("America/New_York")
            try:
                game_date_et = datetime.strptime(game_log["game_date"], "%b %d, %Y")
            except (ValueError, TypeError):
                try:
                    game_date_et = datetime.strptime(game_log["game_date"], "%Y-%m-%d")
                except (ValueError, TypeError):
                    game_date_et = datetime.now(timezone.utc).replace(tzinfo=None)
                    game_date = game_date_et
                    raise  # Re-raise to skip timezone conversion for fallback
            
            # Convert Eastern to UTC
            game_date_et = game_date_et.replace(tzinfo=eastern)
            game_date = game_date_et.astimezone(timezone.utc).replace(tzinfo=None)  # Store as naive UTC
        except:
            pass  # game_date already set to fallback
        
        game = Game(
            nba_game_id=nba_game_id,
            season=season,
            season_type=season_type,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            start_time_utc=game_date,
            status="final" if game_log.get("win_loss") else "scheduled",
        )
        
        db.add(game)
        await db.commit()
        await db.refresh(game)
        
        return game

