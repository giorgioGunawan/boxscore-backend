"""Admin CMS API for direct data editing."""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Player, PlayerSeasonStats, Game, TeamStandings, Team
from app.config import get_settings

router = APIRouter(prefix="/admin/data", tags=["admin-data"])
settings = get_settings()


# ============ Pydantic Models ============

class PlayerCreate(BaseModel):
    nba_player_id: int
    full_name: str
    team_id: Optional[int] = None
    position: Optional[str] = None
    jersey_number: Optional[str] = None


class PlayerUpdate(BaseModel):
    full_name: Optional[str] = None
    team_id: Optional[int] = None
    position: Optional[str] = None
    jersey_number: Optional[str] = None


class PlayerStatsCreate(BaseModel):
    player_id: int
    season: str
    season_type: str = "Regular Season"
    pts: float = 0.0
    reb: float = 0.0
    ast: float = 0.0
    stl: float = 0.0
    blk: float = 0.0
    games_played: int = 0
    fg_pct: Optional[float] = None
    fg3_pct: Optional[float] = None
    ft_pct: Optional[float] = None


class PlayerStatsUpdate(BaseModel):
    pts: Optional[float] = None
    reb: Optional[float] = None
    ast: Optional[float] = None
    stl: Optional[float] = None
    blk: Optional[float] = None
    games_played: Optional[int] = None
    fg_pct: Optional[float] = None
    fg3_pct: Optional[float] = None
    ft_pct: Optional[float] = None


class GameCreate(BaseModel):
    home_team_id: int
    away_team_id: int
    season: str
    season_type: str = "Regular Season"
    game_date: str  # YYYY-MM-DD
    game_time: str = "19:30"  # HH:MM
    status: str = "scheduled"
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class GameUpdate(BaseModel):
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: Optional[str] = None
    game_date: Optional[str] = None
    game_time: Optional[str] = None


class StandingsUpdate(BaseModel):
    wins: Optional[int] = None
    losses: Optional[int] = None
    conference_rank: Optional[int] = None
    streak: Optional[str] = None


# ============ Players ============

@router.get("/players")
async def list_players(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db)
):
    """List all players in the database."""
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.team))
        .offset(offset)
        .limit(limit)
    )
    players = result.scalars().all()
    
    return {
        "players": [
            {
                "id": p.id,
                "nba_player_id": p.nba_player_id,
                "full_name": p.full_name,
                "team": p.team.abbreviation if p.team else None,
                "team_id": p.team_id,
                "position": p.position,
                "jersey_number": p.jersey_number,
            }
            for p in players
        ],
        "count": len(players),
    }


@router.post("/players")
async def create_player(
    data: PlayerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new player."""
    # Check if player already exists
    result = await db.execute(
        select(Player).where(Player.nba_player_id == data.nba_player_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Player with this NBA ID already exists")
    
    player = Player(
        nba_player_id=data.nba_player_id,
        full_name=data.full_name,
        team_id=data.team_id,
        position=data.position,
        jersey_number=data.jersey_number,
        source="manual",
        created_at=datetime.utcnow(),
    )
    db.add(player)
    await db.commit()
    await db.refresh(player)
    
    return {"id": player.id, "message": "Player created"}


@router.put("/players/{player_id}")
async def update_player(
    player_id: int,
    data: PlayerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a player."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    if data.full_name is not None:
        player.full_name = data.full_name
    if data.team_id is not None:
        player.team_id = data.team_id
    if data.position is not None:
        player.position = data.position
    if data.jersey_number is not None:
        player.jersey_number = data.jersey_number
    
    player.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"id": player.id, "message": "Player updated"}


@router.delete("/players/{player_id}")
async def delete_player(
    player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a player."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    await db.delete(player)
    await db.commit()
    
    return {"message": "Player deleted"}


# ============ Player Stats ============

@router.get("/player-stats")
async def list_player_stats(
    player_id: Optional[int] = None,
    season: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List player season stats."""
    query = select(PlayerSeasonStats).options(selectinload(PlayerSeasonStats.player))
    
    if player_id:
        query = query.where(PlayerSeasonStats.player_id == player_id)
    if season:
        query = query.where(PlayerSeasonStats.season == season)
    
    result = await db.execute(query)
    stats = result.scalars().all()
    
    return {
        "stats": [
            {
                "id": s.id,
                "player_id": s.player_id,
                "player_name": s.player.full_name if s.player else None,
                "season": s.season,
                "pts": s.pts,
                "reb": s.reb,
                "ast": s.ast,
                "stl": s.stl,
                "blk": s.blk,
                "games_played": s.games_played,
                "fg_pct": s.fg_pct,
                "fg3_pct": s.fg3_pct,
                "ft_pct": s.ft_pct,
            }
            for s in stats
        ],
        "count": len(stats),
    }


@router.post("/player-stats")
async def create_player_stats(
    data: PlayerStatsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create player season stats."""
    # Check if stats already exist
    result = await db.execute(
        select(PlayerSeasonStats).where(
            PlayerSeasonStats.player_id == data.player_id,
            PlayerSeasonStats.season == data.season,
            PlayerSeasonStats.season_type == data.season_type,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Stats for this player/season already exist")
    
    stats = PlayerSeasonStats(
        player_id=data.player_id,
        season=data.season,
        season_type=data.season_type,
        pts=data.pts,
        reb=data.reb,
        ast=data.ast,
        stl=data.stl,
        blk=data.blk,
        games_played=data.games_played,
        minutes=0.0,
        fg_pct=data.fg_pct,
        fg3_pct=data.fg3_pct,
        ft_pct=data.ft_pct,
        source="manual",
        created_at=datetime.utcnow(),
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)
    
    return {"id": stats.id, "message": "Stats created"}


@router.put("/player-stats/{stats_id}")
async def update_player_stats(
    stats_id: int,
    data: PlayerStatsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update player season stats."""
    result = await db.execute(select(PlayerSeasonStats).where(PlayerSeasonStats.id == stats_id))
    stats = result.scalar_one_or_none()
    
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found")
    
    if data.pts is not None:
        stats.pts = data.pts
    if data.reb is not None:
        stats.reb = data.reb
    if data.ast is not None:
        stats.ast = data.ast
    if data.stl is not None:
        stats.stl = data.stl
    if data.blk is not None:
        stats.blk = data.blk
    if data.games_played is not None:
        stats.games_played = data.games_played
    if data.fg_pct is not None:
        stats.fg_pct = data.fg_pct
    if data.fg3_pct is not None:
        stats.fg3_pct = data.fg3_pct
    if data.ft_pct is not None:
        stats.ft_pct = data.ft_pct
    
    stats.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"id": stats.id, "message": "Stats updated"}


@router.delete("/player-stats/{stats_id}")
async def delete_player_stats(
    stats_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete player season stats."""
    result = await db.execute(select(PlayerSeasonStats).where(PlayerSeasonStats.id == stats_id))
    stats = result.scalar_one_or_none()
    
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found")
    
    await db.delete(stats)
    await db.commit()
    
    return {"message": "Stats deleted"}


# ============ Games ============

@router.get("/games")
async def list_games(
    team_id: Optional[int] = None,
    season: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """List games."""
    query = (
        select(Game)
        .options(selectinload(Game.home_team), selectinload(Game.away_team))
        .order_by(Game.start_time_utc.desc())
        .limit(limit)
    )
    
    if team_id:
        query = query.where((Game.home_team_id == team_id) | (Game.away_team_id == team_id))
    if season:
        query = query.where(Game.season == season)
    if status:
        query = query.where(Game.status == status)
    
    result = await db.execute(query)
    games = result.scalars().all()
    
    return {
        "games": [
            {
                "id": g.id,
                "nba_game_id": g.nba_game_id,
                "home_team": g.home_team.abbreviation if g.home_team else None,
                "away_team": g.away_team.abbreviation if g.away_team else None,
                "home_team_id": g.home_team_id,
                "away_team_id": g.away_team_id,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "status": g.status,
                "game_date": g.start_time_utc.strftime("%Y-%m-%d") if g.start_time_utc else None,
                "game_time": g.start_time_utc.strftime("%H:%M") if g.start_time_utc else None,
                "season": g.season,
            }
            for g in games
        ],
        "count": len(games),
    }


@router.post("/games")
async def create_game(
    data: GameCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new game."""
    # Parse date/time
    game_datetime = datetime.strptime(f"{data.game_date} {data.game_time}", "%Y-%m-%d %H:%M")
    
    game = Game(
        nba_game_id=f"MANUAL-{int(datetime.now().timestamp())}",
        home_team_id=data.home_team_id,
        away_team_id=data.away_team_id,
        season=data.season,
        season_type=data.season_type,
        start_time_utc=game_datetime,
        status=data.status,
        home_score=data.home_score,
        away_score=data.away_score,
        source="manual",
        created_at=datetime.utcnow(),
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)
    
    return {"id": game.id, "message": "Game created"}


@router.put("/games/{game_id}")
async def update_game(
    game_id: int,
    data: GameUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a game."""
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if data.home_score is not None:
        game.home_score = data.home_score
    if data.away_score is not None:
        game.away_score = data.away_score
    if data.status is not None:
        game.status = data.status
    if data.game_date and data.game_time:
        game.start_time_utc = datetime.strptime(f"{data.game_date} {data.game_time}", "%Y-%m-%d %H:%M")
    
    game.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"id": game.id, "message": "Game updated"}


@router.delete("/games/{game_id}")
async def delete_game(
    game_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a game."""
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    await db.delete(game)
    await db.commit()
    
    return {"message": "Game deleted"}


# ============ Standings ============

@router.get("/standings")
async def list_standings(
    season: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List team standings."""
    query = select(TeamStandings).options(selectinload(TeamStandings.team))
    
    if season:
        query = query.where(TeamStandings.season == season)
    else:
        query = query.where(TeamStandings.season == settings.current_season)
    
    result = await db.execute(query)
    standings = result.scalars().all()
    
    return {
        "standings": [
            {
                "id": s.id,
                "team_id": s.team_id,
                "team": s.team.abbreviation if s.team else None,
                "team_name": s.team.name if s.team else None,
                "season": s.season,
                "wins": s.wins,
                "losses": s.losses,
                "conference_rank": s.conference_rank,
                "streak": s.streak,
            }
            for s in standings
        ],
        "count": len(standings),
    }


@router.put("/standings/{team_id}")
async def update_standings(
    team_id: int,
    data: StandingsUpdate,
    season: str = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Update team standings."""
    season = season or settings.current_season
    
    result = await db.execute(
        select(TeamStandings).where(
            TeamStandings.team_id == team_id,
            TeamStandings.season == season,
        )
    )
    standings = result.scalar_one_or_none()
    
    if not standings:
        # Create new standings
        standings = TeamStandings(
            team_id=team_id,
            season=season,
            season_type="Regular Season",
            wins=data.wins or 0,
            losses=data.losses or 0,
            conference_rank=data.conference_rank or 1,
            streak=data.streak,
            source="manual",
            created_at=datetime.utcnow(),
        )
        db.add(standings)
    else:
        if data.wins is not None:
            standings.wins = data.wins
        if data.losses is not None:
            standings.losses = data.losses
        if data.conference_rank is not None:
            standings.conference_rank = data.conference_rank
        if data.streak is not None:
            standings.streak = data.streak
        standings.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"team_id": team_id, "message": "Standings updated"}


# ============ Teams (read-only, for reference) ============

@router.get("/teams")
async def list_teams(db: AsyncSession = Depends(get_db)):
    """List all teams (for reference when editing)."""
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    
    return {
        "teams": [
            {
                "id": t.id,
                "nba_team_id": t.nba_team_id,
                "name": t.name,
                "abbreviation": t.abbreviation,
                "conference": t.conference,
            }
            for t in teams
        ],
        "count": len(teams),
    }
