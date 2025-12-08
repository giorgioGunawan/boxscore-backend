"""
NBA API Client wrapper.

Wraps the nba_api library to provide normalized data for our backend.
All methods run synchronously (nba_api is sync) but return normalized dicts.
"""
import time
from datetime import datetime
from typing import Optional
from functools import wraps
import pandas as pd

from nba_api.stats.static import teams as nba_teams, players as nba_players
from nba_api.stats.endpoints import (
    leaguegamefinder,
    playercareerstats,
    playergamelog,
    leaguestandings,
    scoreboardv2,
    commonplayerinfo,
    scheduleleaguev2,
    commonteamroster,
)

from app.cache import increment_upstream_calls


def rate_limited(func):
    """Rate limit decorator with retry logic to handle NBA API flakiness."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                time.sleep(0.6 + (attempt * 0.5))  # Increase delay on retries
                increment_upstream_calls()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                print(f"NBA API attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1.0)  # Extra delay before retry
                continue
        
        # All retries failed
        print(f"NBA API call failed after {max_retries} attempts: {last_error}")
        raise last_error
    return wrapper


class NBAClient:
    """Client for fetching data from NBA API."""
    
    # Static team/player data
    @staticmethod
    def get_all_teams() -> list[dict]:
        """Get all NBA teams (static data)."""
        teams = nba_teams.get_teams()
        return [
            {
                "nba_team_id": t["id"],
                "name": t["full_name"],
                "abbreviation": t["abbreviation"],
                "conference": _get_conference(t["abbreviation"]),
                "division": _get_division(t["abbreviation"]),
            }
            for t in teams
        ]
    
    @staticmethod
    def get_team_by_abbreviation(abbr: str) -> Optional[dict]:
        """Get team by abbreviation."""
        teams = nba_teams.find_teams_by_abbreviation(abbr)
        if teams:
            t = teams[0]
            return {
                "nba_team_id": t["id"],
                "name": t["full_name"],
                "abbreviation": t["abbreviation"],
                "conference": _get_conference(t["abbreviation"]),
                "division": _get_division(t["abbreviation"]),
            }
        return None
    
    @staticmethod
    def search_players(name: str) -> list[dict]:
        """Search for players by name."""
        players = nba_players.find_players_by_full_name(name)
        return [
            {
                "nba_player_id": p["id"],
                "full_name": p["full_name"],
                "is_active": p["is_active"],
            }
            for p in players
        ]
    
    @staticmethod
    def get_all_active_players() -> list[dict]:
        """Get all active NBA players."""
        players = nba_players.get_active_players()
        return [
            {
                "nba_player_id": p["id"],
                "full_name": p["full_name"],
            }
            for p in players
        ]
    
    # Dynamic data (requires API calls)
    @staticmethod
    @rate_limited
    def get_team_games(
        team_id: int,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> list[dict]:
        """
        Get all PLAYED games for a team in a season.
        Returns normalized game data.
        Note: This only returns past games, not future scheduled games.
        """
        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_id,
            season_nullable=season,
            season_type_nullable=season_type,
        )
        
        games_df = finder.get_data_frames()[0]
        games = []
        
        for _, row in games_df.iterrows():
            matchup = row["MATCHUP"]
            is_home = "@" not in matchup
            
            # Parse opponent from matchup (e.g., "GSW vs. LAL" or "GSW @ LAL")
            parts = matchup.replace("vs.", "@").split("@")
            opponent_abbr = parts[1].strip() if len(parts) > 1 else ""
            
            games.append({
                "nba_game_id": row["GAME_ID"],
                "game_date": row["GAME_DATE"],
                "matchup": matchup,
                "is_home": is_home,
                "opponent_abbr": opponent_abbr,
                "team_score": row.get("PTS"),
                "win_loss": row.get("WL"),
                "season": season,
                "season_type": season_type,
            })
        
        return games
    
    @staticmethod
    @rate_limited
    def get_team_schedule(
        team_id: int,
        season: str = "2024-25"
    ) -> list[dict]:
        """
        Get full season schedule for a team (past and future games).
        Uses the ScheduleLeagueV2 endpoint.
        """
        import warnings
        warnings.filterwarnings('ignore')
        
        schedule = scheduleleaguev2.ScheduleLeagueV2(season=season)
        df = schedule.get_data_frames()[0]
        
        # Filter for this team
        team_games = df[(df['homeTeam_teamId'] == team_id) | (df['awayTeam_teamId'] == team_id)]
        
        games = []
        for _, row in team_games.iterrows():
            is_home = row['homeTeam_teamId'] == team_id
            opponent_id = row['awayTeam_teamId'] if is_home else row['homeTeam_teamId']
            opponent_abbr = row['awayTeam_teamTricode'] if is_home else row['homeTeam_teamTricode']
            
            # Parse date and time
            # NBA API provides gameDateTimeUTC directly - use that!
            # gameDateTimeUTC is the correct UTC datetime (e.g., "2025-12-09T00:00:00Z")
            # This is the authoritative source - don't use gameTimeEst which is Eastern Time!
            game_datetime_utc_str = None
            if 'gameDateTimeUTC' in row and pd.notna(row.get('gameDateTimeUTC')):
                game_datetime_utc_str = str(row['gameDateTimeUTC'])
            
            # Extract date and time portions from UTC datetime
            if game_datetime_utc_str:
                game_datetime_utc = game_datetime_utc_str
                # Parse: "2025-12-09T00:00:00Z" -> date="2025-12-09", time="00:00"
                if 'T' in game_datetime_utc_str:
                    date_part, time_part = game_datetime_utc_str.split('T')
                    game_date = date_part
                    # Extract HH:MM from time part (remove Z, +00:00, etc.)
                    time_clean = time_part.replace('Z', '').replace('+00:00', '').split('.')[0]
                    game_time = time_clean[:5] if len(time_clean) >= 5 else time_clean
                else:
                    game_date = ""
                    game_time = ""
            else:
                # Fallback: shouldn't happen, but handle gracefully
                game_date = str(row['gameDateEst']).split('T')[0] if pd.notna(row.get('gameDateEst')) else ""
                game_time = ""
                game_datetime_utc = None
            
            # Determine status: 1=scheduled, 2=in_progress, 3=final
            status_id = row.get('gameStatus', 1)
            if status_id == 3:
                status = "final"
            elif status_id == 2:
                status = "in_progress"
            else:
                status = "scheduled"
            
            games.append({
                "nba_game_id": row['gameId'],
                "game_date": game_date,
                "game_time": game_time,
                "game_datetime_utc": game_datetime_utc,  # Full UTC datetime string from API
                "is_home": is_home,
                "opponent_nba_id": opponent_id,
                "opponent_abbr": opponent_abbr,
                "opponent_name": row['awayTeam_teamName'] if is_home else row['homeTeam_teamName'],
                "home_score": row.get('homeTeam_score'),
                "away_score": row.get('awayTeam_score'),
                "status": status,
                "arena": row.get('arenaName', ''),
            })
        
        return games
    
    @staticmethod
    @rate_limited
    def get_team_roster(
        team_id: int,
        season: str = "2024-25"
    ) -> list[dict]:
        """
        Get team roster for a season.
        Returns list of players with their info.
        """
        try:
            roster = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season
            )
            df = roster.get_data_frames()[0]
            
            players = []
            for _, row in df.iterrows():
                players.append({
                    "nba_player_id": row["PLAYER_ID"],
                    "name": row["PLAYER"],
                    "number": row["NUM"],
                    "position": row["POSITION"],
                    "height": row["HEIGHT"],
                    "weight": row["WEIGHT"],
                    "age": row["AGE"],
                    "experience": row["EXP"],
                    "school": row["SCHOOL"],
                })
            
            return players
        except Exception as e:
            print(f"Error getting roster for team {team_id}: {e}")
            return []
    
    @staticmethod
    @rate_limited
    def get_game_by_id(game_id: str) -> Optional[dict]:
        """
        Get detailed game info by game ID using boxscore.
        Returns both teams' scores.
        """
        try:
            # Try BoxScoreSummaryV3 first (newer, more reliable)
            try:
                from nba_api.stats.endpoints import boxscoresummaryv3
                import warnings
                warnings.filterwarnings('ignore')
                
                box = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id)
                data = box.get_dict()
                
                # V3 has different structure
                if 'boxScoreSummary' in data:
                    summary = data['boxScoreSummary']
                    home_team = summary.get('homeTeam', {})
                    away_team = summary.get('awayTeam', {})
                    
                    return {
                        "nba_game_id": game_id,
                        "home_team_id": home_team.get('teamId'),
                        "away_team_id": away_team.get('teamId'),
                        "home_score": home_team.get('score'),
                        "away_score": away_team.get('score'),
                        "game_status": summary.get('gameStatusText', ''),
                    }
            except Exception:
                pass
            
            # Fallback to V2
            from nba_api.stats.endpoints import boxscoresummaryv2
            import warnings
            warnings.filterwarnings('ignore')
            
            box = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
            game_summary = box.get_data_frames()[0]  # GameSummary
            line_score = box.get_data_frames()[5]  # LineScore
            
            if game_summary.empty:
                return None
            
            summary = game_summary.iloc[0]
            
            # Get scores from line score
            home_score = away_score = None
            home_team_id = summary.get("HOME_TEAM_ID")
            away_team_id = summary.get("VISITOR_TEAM_ID")
            
            for _, row in line_score.iterrows():
                if row.get("TEAM_ID") == home_team_id:
                    home_score = row.get("PTS")
                elif row.get("TEAM_ID") == away_team_id:
                    away_score = row.get("PTS")
            
            return {
                "nba_game_id": game_id,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "game_status": summary.get("GAME_STATUS_TEXT", ""),
            }
        except Exception as e:
            print(f"Error getting game {game_id}: {e}")
            return None
    
    @staticmethod
    @rate_limited
    def get_game_boxscore_with_players(game_id: str) -> Optional[dict]:
        """
        Get complete box score for a game including ALL player stats.
        This is MUCH more efficient than fetching each player's game log individually.
        
        Returns:
        {
            "game_status": "Final",
            "home_score": 120,
            "away_score": 115,
            "player_stats": [
                {
                    "nba_player_id": 201939,
                    "player_name": "Stephen Curry",
                    "team_id": 1610612744,
                    "pts": 30,
                    "reb": 5,
                    "ast": 8,
                    "stl": 2,
                    "blk": 0,
                    "minutes": "35:24",
                    ...
                },
                ...
            ]
        }
        """
        try:
            # Use BoxScoreTraditionalV2 (most reliable for player stats)
            from nba_api.stats.endpoints import boxscoretraditionalv2
            import warnings
            warnings.filterwarnings('ignore')
            
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            dfs = box.get_data_frames()
            
            # Index 0: PlayerStats
            # Index 1: TeamStats
            player_stats_df = dfs[0]
            
            player_stats = []
            for _, row in player_stats_df.iterrows():
                # Only include players who actually played (have minutes)
                # Some players might have None or empty string for minutes
                minutes = row.get('MIN')
                if minutes is None or str(minutes).strip() == '' or str(minutes) == '0:00':
                    continue
                
                player_stats.append({
                    "nba_player_id": int(row.get('PLAYER_ID', 0)),
                    "player_name": row.get('PLAYER_NAME', ''),
                    "team_id": int(row.get('TEAM_ID', 0)),
                    "pts": int(row.get('PTS', 0) or 0),
                    "reb": int(row.get('REB', 0) or 0),
                    "ast": int(row.get('AST', 0) or 0),
                    "stl": int(row.get('STL', 0) or 0),
                    "blk": int(row.get('BLK', 0) or 0),
                    "minutes": str(minutes),
                })
            
            # Get game status from summary
            game_info = NBAClient.get_game_by_id(game_id)
            game_status = game_info.get('game_status', 'Unknown') if game_info else 'Unknown'
            home_score = game_info.get('home_score') if game_info else None
            away_score = game_info.get('away_score') if game_info else None
            
            return {
                "game_status": game_status,
                "home_score": home_score,
                "away_score": away_score,
                "player_stats": player_stats
            }
            
        except Exception as e:
            print(f"Error getting box score for game {game_id}: {e}")
            return None
    
    @staticmethod
    @rate_limited
    def get_player_career_stats(
        player_id: int,
        per_mode: str = "PerGame"
    ) -> dict:
        """
        Get player career stats including current season.
        Returns per-game averages.
        """
        career = playercareerstats.PlayerCareerStats(
            player_id=player_id,
            per_mode36=per_mode,
        )
        
        # Get regular season stats
        season_df = career.get_data_frames()[0]  # SeasonTotalsRegularSeason
        
        if season_df.empty:
            return {"seasons": []}
        
        seasons = []
        for _, row in season_df.iterrows():
            seasons.append({
                "season": row["SEASON_ID"],
                "team_abbr": row.get("TEAM_ABBREVIATION", ""),
                "games_played": row.get("GP", 0),
                "minutes": row.get("MIN", 0),
                "pts": row.get("PTS", 0),
                "reb": row.get("REB", 0),
                "ast": row.get("AST", 0),
                "stl": row.get("STL", 0),
                "blk": row.get("BLK", 0),
                "fg_pct": row.get("FG_PCT"),
                "fg3_pct": row.get("FG3_PCT"),
                "ft_pct": row.get("FT_PCT"),
            })
        
        return {"seasons": seasons}
    
    @staticmethod
    @rate_limited
    def get_player_game_log(
        player_id: int,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> list[dict]:
        """
        Get player's game log for a season.
        """
        log = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star=season_type,
        )
        
        log_df = log.get_data_frames()[0]
        games = []
        
        for _, row in log_df.iterrows():
            matchup = row.get("MATCHUP", "")
            is_home = "@" not in matchup
            parts = matchup.replace("vs.", "@").split("@")
            opponent_abbr = parts[1].strip() if len(parts) > 1 else ""
            
            games.append({
                "nba_game_id": row["Game_ID"],
                "game_date": row["GAME_DATE"],
                "matchup": matchup,
                "is_home": is_home,
                "opponent_abbr": opponent_abbr,
                "pts": row.get("PTS", 0),
                "reb": row.get("REB", 0),
                "ast": row.get("AST", 0),
                "stl": row.get("STL", 0),
                "blk": row.get("BLK", 0),
                "minutes": row.get("MIN", "0"),
                "fgm": row.get("FGM", 0),
                "fga": row.get("FGA", 0),
                "fg3m": row.get("FG3M", 0),
                "fg3a": row.get("FG3A", 0),
                "ftm": row.get("FTM", 0),
                "fta": row.get("FTA", 0),
                "plus_minus": row.get("PLUS_MINUS", 0),
                "turnovers": row.get("TOV", 0),
                "win_loss": row.get("WL"),
            })
        
        return games
    
    @staticmethod
    @rate_limited
    def get_league_standings(
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> list[dict]:
        """
        Get current league standings.
        """
        standings = leaguestandings.LeagueStandings(
            season=season,
            season_type=season_type,
        )
        
        standings_df = standings.get_data_frames()[0]
        result = []
        
        for _, row in standings_df.iterrows():
            result.append({
                "nba_team_id": row["TeamID"],
                "team_name": row.get("TeamName", ""),
                "team_city": row.get("TeamCity", ""),
                "conference": row.get("Conference", ""),
                "division": row.get("Division", ""),
                "wins": row.get("WINS", 0),
                "losses": row.get("LOSSES", 0),
                "win_pct": row.get("WinPCT", 0),
                "conference_rank": row.get("PlayoffRank", 0),
                "division_rank": row.get("DivisionRank", 0),
                "games_back": row.get("ConferenceGamesBack", 0),
                "streak": _format_streak(row.get("strCurrentStreak", "")),
                "last_10": f"{row.get('L10', '0-0')}",
            })
        
        return result
    
    @staticmethod
    @rate_limited
    def get_player_info(player_id: int) -> Optional[dict]:
        """Get detailed player info including current team."""
        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            info_df = info.get_data_frames()[0]
            
            if info_df.empty:
                return None
            
            row = info_df.iloc[0]
            return {
                "nba_player_id": player_id,
                "full_name": f"{row.get('FIRST_NAME', '')} {row.get('LAST_NAME', '')}".strip(),
                "team_id": row.get("TEAM_ID"),
                "team_name": row.get("TEAM_NAME", ""),
                "team_abbreviation": row.get("TEAM_ABBREVIATION", ""),
                "position": row.get("POSITION", ""),
                "jersey": row.get("JERSEY", ""),
                "height": row.get("HEIGHT", ""),
                "weight": row.get("WEIGHT", ""),
            }
        except Exception as e:
            print(f"Error getting player info: {e}")
            return None
    
    @staticmethod
    @rate_limited
    def get_todays_scoreboard() -> list[dict]:
        """Get today's games scoreboard."""
        try:
            scoreboard = scoreboardv2.ScoreboardV2()
            games_df = scoreboard.get_data_frames()[0]  # GameHeader
            line_score_df = scoreboard.get_data_frames()[1]  # LineScore
            
            games = []
            for _, row in games_df.iterrows():
                game_id = row["GAME_ID"]
                
                # Get scores from line score
                game_lines = line_score_df[line_score_df["GAME_ID"] == game_id]
                home_score = away_score = None
                home_team_id = away_team_id = None
                
                for _, line in game_lines.iterrows():
                    if line.get("TEAM_ID") == row.get("HOME_TEAM_ID"):
                        home_score = line.get("PTS")
                        home_team_id = line.get("TEAM_ID")
                    else:
                        away_score = line.get("PTS")
                        away_team_id = line.get("TEAM_ID")
                
                games.append({
                    "nba_game_id": game_id,
                    "game_status_text": row.get("GAME_STATUS_TEXT", ""),
                    "game_status_id": row.get("GAME_STATUS_ID", 1),
                    "home_team_id": home_team_id or row.get("HOME_TEAM_ID"),
                    "away_team_id": away_team_id or row.get("VISITOR_TEAM_ID"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "start_time_utc": row.get("GAME_DATE_EST"),
                })
            
            return games
        except Exception as e:
            print(f"Error getting scoreboard: {e}")
            return []


# Helper functions for team conference/division mapping
CONFERENCE_MAP = {
    "ATL": "East", "BOS": "East", "BKN": "East", "CHA": "East", "CHI": "East",
    "CLE": "East", "DET": "East", "IND": "East", "MIA": "East", "MIL": "East",
    "NYK": "East", "ORL": "East", "PHI": "East", "TOR": "East", "WAS": "East",
    "DAL": "West", "DEN": "West", "GSW": "West", "HOU": "West", "LAC": "West",
    "LAL": "West", "MEM": "West", "MIN": "West", "NOP": "West", "OKC": "West",
    "PHX": "West", "POR": "West", "SAC": "West", "SAS": "West", "UTA": "West",
}

DIVISION_MAP = {
    "ATL": "Southeast", "CHA": "Southeast", "MIA": "Southeast", "ORL": "Southeast", "WAS": "Southeast",
    "BOS": "Atlantic", "BKN": "Atlantic", "NYK": "Atlantic", "PHI": "Atlantic", "TOR": "Atlantic",
    "CHI": "Central", "CLE": "Central", "DET": "Central", "IND": "Central", "MIL": "Central",
    "DAL": "Southwest", "HOU": "Southwest", "MEM": "Southwest", "NOP": "Southwest", "SAS": "Southwest",
    "DEN": "Northwest", "MIN": "Northwest", "OKC": "Northwest", "POR": "Northwest", "UTA": "Northwest",
    "GSW": "Pacific", "LAC": "Pacific", "LAL": "Pacific", "PHX": "Pacific", "SAC": "Pacific",
}


def _get_conference(abbr: str) -> str:
    return CONFERENCE_MAP.get(abbr, "Unknown")


def _get_division(abbr: str) -> str:
    return DIVISION_MAP.get(abbr, "Unknown")


def _format_streak(streak: str) -> str:
    """Format streak string."""
    if not streak:
        return ""
    # Already formatted like "W 3" or "L 2"
    return streak.replace(" ", "")

