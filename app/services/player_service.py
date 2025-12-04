"""Player service with cache-aside pattern."""
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Player, PlayerSeasonStats, PlayerGameStats, Game, Team
from app.nba_client import NBAClient
from app.cache import cache_get, cache_set, cache_delete_pattern
from app.config import get_settings
from app.services.team_service import TeamService

settings = get_settings()


class PlayerService:
    """Service for player-related operations."""
    
    @staticmethod
    async def get_or_create_player(
        db: AsyncSession,
        nba_player_id: int,
        full_name: Optional[str] = None
    ) -> Player:
        """Get player from DB or create if not exists."""
        result = await db.execute(
            select(Player).where(Player.nba_player_id == nba_player_id)
        )
        player = result.scalar_one_or_none()
        
        if player:
            return player
        
        # Fetch player info from NBA API
        player_info = NBAClient.get_player_info(nba_player_id)
        
        if player_info:
            # Get team ID if available
            team_id = None
            if player_info.get("team_id"):
                team = await TeamService.get_team_by_nba_id(db, player_info["team_id"])
                if team:
                    team_id = team.id
            
            player = Player(
                nba_player_id=nba_player_id,
                full_name=player_info.get("full_name") or full_name or "Unknown",
                team_id=team_id,
                position=player_info.get("position"),
            )
        else:
            player = Player(
                nba_player_id=nba_player_id,
                full_name=full_name or "Unknown",
            )
        
        db.add(player)
        await db.commit()
        await db.refresh(player)
        return player
    
    @staticmethod
    async def get_player_by_id(db: AsyncSession, player_id: int) -> Optional[dict]:
        """Get player by internal ID."""
        result = await db.execute(
            select(Player)
            .options(selectinload(Player.team))
            .where(Player.id == player_id)
        )
        player = result.scalar_one_or_none()
        
        if not player:
            return None
        
        return {
            "id": player.id,
            "nba_player_id": player.nba_player_id,
            "full_name": player.full_name,
            "position": player.position,
            "team": {
                "id": player.team.id,
                "name": player.team.name,
                "abbreviation": player.team.abbreviation,
            } if player.team else None,
        }
    
    @staticmethod
    async def get_player_by_nba_id(db: AsyncSession, nba_player_id: int) -> Optional[dict]:
        """Get player by NBA player ID."""
        result = await db.execute(
            select(Player)
            .options(selectinload(Player.team))
            .where(Player.nba_player_id == nba_player_id)
        )
        player = result.scalar_one_or_none()
        
        if not player:
            return None
        
        return {
            "id": player.id,
            "nba_player_id": player.nba_player_id,
            "full_name": player.full_name,
            "position": player.position,
            "team": {
                "id": player.team.id,
                "name": player.team.name,
                "abbreviation": player.team.abbreviation,
            } if player.team else None,
        }
    
    @staticmethod
    async def search_players(name: str) -> list[dict]:
        """Search for players by name (uses static NBA API data)."""
        return NBAClient.search_players(name)
    
    @staticmethod
    async def get_player_season_averages(
        db: AsyncSession,
        player_id: int,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> Optional[dict]:
        """
        Get player's season averages.
        Cache-aside pattern: check cache -> DB -> NBA API on miss.
        """
        season = season or settings.current_season
        cache_key = f"player:{player_id}:season_avg:{season}:{season_type}"
        
        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # Get player from DB
        result = await db.execute(
            select(Player).where(Player.id == player_id)
        )
        player = result.scalar_one_or_none()
        
        if not player:
            return None
        
        # Check DB for stats
        result = await db.execute(
            select(PlayerSeasonStats).where(
                PlayerSeasonStats.player_id == player_id,
                PlayerSeasonStats.season == season,
                PlayerSeasonStats.season_type == season_type,
            )
        )
        stats = result.scalar_one_or_none()
        
        # If not in DB or forcing refresh, fetch from NBA API
        if not stats or force_refresh:
            career_data = NBAClient.get_player_career_stats(player.nba_player_id)
            
            # Find the matching season
            season_data = None
            for s in career_data.get("seasons", []):
                if s["season"] == season:
                    season_data = s
                    break
            
            if season_data:
                if stats:
                    # Update existing
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
                else:
                    # Create new
                    stats = PlayerSeasonStats(
                        player_id=player_id,
                        season=season,
                        season_type=season_type,
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
                    )
                    db.add(stats)
                
                await db.commit()
                await db.refresh(stats)
        
        if not stats:
            return None
        
        # Build response
        response = {
            "player_id": player_id,
            "player_name": player.full_name,
            "season": season,
            "season_type": season_type,
            "ppg": round(stats.pts, 1),
            "rpg": round(stats.reb, 1),
            "apg": round(stats.ast, 1),
            "spg": round(stats.stl, 1),
            "bpg": round(stats.blk, 1),
            "games_played": stats.games_played,
            "minutes": round(stats.minutes, 1),
            "fg_pct": round(stats.fg_pct * 100, 1) if stats.fg_pct else None,
            "fg3_pct": round(stats.fg3_pct * 100, 1) if stats.fg3_pct else None,
            "ft_pct": round(stats.ft_pct * 100, 1) if stats.ft_pct else None,
        }
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_player_stats)
        
        return response
    
    @staticmethod
    async def get_player_latest_game(
        db: AsyncSession,
        player_id: int,
        season: Optional[str] = None,
        season_type: str = "Regular Season",
        force_refresh: bool = False
    ) -> Optional[dict]:
        """
        Get player's most recent game stats.
        If no data for current season, will try to find most recent game.
        """
        original_season = season or settings.current_season
        cache_key = f"player:{player_id}:latest_game:{original_season}:{season_type}"
        
        # Check cache first
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        season = original_season
        
        # Get player from DB
        result = await db.execute(
            select(Player).where(Player.id == player_id)
        )
        player = result.scalar_one_or_none()
        
        if not player:
            return None
        
        # Get latest game stats from DB
        result = await db.execute(
            select(PlayerGameStats)
            .options(selectinload(PlayerGameStats.game).selectinload(Game.home_team))
            .options(selectinload(PlayerGameStats.game).selectinload(Game.away_team))
            .join(Game)
            .where(
                PlayerGameStats.player_id == player_id,
                Game.season == season,
                Game.status == "final",
            )
            .order_by(Game.start_time_utc.desc())
            .limit(1)
        )
        game_stats = result.scalar_one_or_none()
        
        # Track game log for later use
        game_log = []
        
        # If not in DB or forcing refresh, fetch from NBA API
        if not game_stats or force_refresh:
            # Try current season first, then fall back to previous seasons
            seasons_to_try = [season]
            # Add previous seasons as fallback (e.g., 2025-26 -> 2024-25 -> 2023-24)
            try:
                year = int(season.split("-")[0])
                for i in range(1, 3):  # Try up to 2 previous seasons
                    prev_year = year - i
                    prev_season = f"{prev_year}-{str(prev_year + 1)[-2:]}"
                    seasons_to_try.append(prev_season)
            except (ValueError, IndexError):
                pass
            
            game_log = []
            actual_season = season
            for try_season in seasons_to_try:
                game_log = NBAClient.get_player_game_log(
                    player.nba_player_id,
                    season=try_season,
                    season_type=season_type,
                )
                if game_log:
                    actual_season = try_season
                    break
            
            if game_log:
                # Import here to avoid circular imports
                from app.services.game_service import GameService
                
                # Get the latest game
                latest = game_log[0]
                
                # Get team ID - either from player or by looking up from matchup
                team_id_for_game = player.team_id
                if not team_id_for_game:
                    # Try to get team from the matchup (e.g., "LAL vs. GSW" -> LAL)
                    matchup = latest.get("matchup", "")
                    if matchup:
                        team_abbr = matchup.split()[0] if matchup else ""
                        team_abbr_map = await TeamService.get_team_abbr_map(db)
                        team_id_for_game = team_abbr_map.get(team_abbr)
                
                # Ensure game exists in DB
                game = await GameService.get_or_create_game_from_log(
                    db, latest, team_id_for_game, actual_season, season_type
                )
                
                if game:
                    # Upsert player game stats
                    result = await db.execute(
                        select(PlayerGameStats).where(
                            PlayerGameStats.player_id == player_id,
                            PlayerGameStats.game_id == game.id,
                        )
                    )
                    game_stats = result.scalar_one_or_none()
                    
                    if not game_stats:
                        game_stats = PlayerGameStats(
                            player_id=player_id,
                            game_id=game.id,
                        )
                        db.add(game_stats)
                    
                    game_stats.pts = latest["pts"]
                    game_stats.reb = latest["reb"]
                    game_stats.ast = latest["ast"]
                    game_stats.stl = latest["stl"]
                    game_stats.blk = latest["blk"]
                    game_stats.minutes = str(latest.get("minutes", "0"))
                    game_stats.fgm = latest.get("fgm")
                    game_stats.fga = latest.get("fga")
                    game_stats.fg3m = latest.get("fg3m")
                    game_stats.fg3a = latest.get("fg3a")
                    game_stats.ftm = latest.get("ftm")
                    game_stats.fta = latest.get("fta")
                    game_stats.plus_minus = latest.get("plus_minus")
                    game_stats.turnovers = latest.get("turnovers")
                    
                    await db.commit()
                    await db.refresh(game_stats)
                    
                    # Reload with relationships
                    result = await db.execute(
                        select(PlayerGameStats)
                        .options(selectinload(PlayerGameStats.game).selectinload(Game.home_team))
                        .options(selectinload(PlayerGameStats.game).selectinload(Game.away_team))
                        .where(PlayerGameStats.id == game_stats.id)
                    )
                    game_stats = result.scalar_one_or_none()
        
        if not game_stats or not game_stats.game:
            return None
        
        game = game_stats.game
        
        # Determine opponent - handle case where player.team_id might be None
        # Use the game data to determine which team the player was on
        player_team_id = player.team_id
        
        # If player has no team, try to determine from the game log we fetched
        if not player_team_id and game_log:
            matchup = game_log[0].get("matchup", "") if game_log else ""
            if matchup:
                team_abbr = matchup.split()[0] if matchup else ""
                team_abbr_map = await TeamService.get_team_abbr_map(db)
                player_team_id = team_abbr_map.get(team_abbr)
        
        if player_team_id:
            if player_team_id == game.home_team_id:
                opponent = game.away_team
                is_home = True
            else:
                opponent = game.home_team
                is_home = False
        else:
            # If still no team, just show both teams
            opponent = game.away_team
            is_home = True
        
        response = {
            "player_id": player_id,
            "player_name": player.full_name,
            "season": game.season,
            "game_date": game.start_time_utc.strftime("%d %b %Y"),
            "opponent": opponent.abbreviation if opponent else "???",
            "is_home": is_home,
            "pts": game_stats.pts,
            "reb": game_stats.reb,
            "ast": game_stats.ast,
            "stl": game_stats.stl,
            "blk": game_stats.blk,
            "minutes": game_stats.minutes,
            "result": _determine_result(game, player_team_id) if player_team_id else None,
        }
        
        # Cache the response
        await cache_set(cache_key, response, settings.cache_ttl_player_game)
        
        return response


def _determine_result(game: Game, team_id: int) -> Optional[str]:
    """Determine if team won or lost."""
    if game.home_score is None or game.away_score is None:
        return None
    
    if team_id == game.home_team_id:
        return "W" if game.home_score > game.away_score else "L"
    else:
        return "W" if game.away_score > game.home_score else "L"

