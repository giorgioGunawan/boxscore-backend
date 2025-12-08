"""Admin CMS API for direct data editing."""
import zoneinfo
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Player, PlayerSeasonStats, Game, TeamStandings, Team, PlayerGameStats
from app.config import get_settings
from sqlalchemy import func, or_

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
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    search: Optional[str] = Query(default=None),
    team_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """List all players in the database with search and pagination."""
    query = select(Player).options(selectinload(Player.team))
    
    # Search by name
    if search:
        query = query.where(Player.full_name.ilike(f"%{search}%"))
    
    # Filter by team
    if team_id:
        query = query.where(Player.team_id == team_id)
    
    # Get total count
    count_query = select(func.count(Player.id))
    if search:
        count_query = count_query.where(Player.full_name.ilike(f"%{search}%"))
    if team_id:
        count_query = count_query.where(Player.team_id == team_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Get paginated results
    query = query.order_by(Player.full_name).offset(offset).limit(limit)
    result = await db.execute(query)
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
        "total": total,
        "offset": offset,
        "limit": limit,
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
    search: Optional[str] = Query(default=None),
    team_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db)
):
    """List player season stats with search and pagination."""
    query = select(PlayerSeasonStats).options(selectinload(PlayerSeasonStats.player))
    
    if player_id:
        query = query.where(PlayerSeasonStats.player_id == player_id)
    if season:
        query = query.where(PlayerSeasonStats.season == season)
    if search:
        query = query.join(Player).where(Player.full_name.ilike(f"%{search}%"))
    if team_id:
        query = query.join(Player).where(Player.team_id == team_id)
    
    # Get total count
    count_query = select(func.count(PlayerSeasonStats.id))
    if player_id:
        count_query = count_query.where(PlayerSeasonStats.player_id == player_id)
    if season:
        count_query = count_query.where(PlayerSeasonStats.season == season)
    if search:
        count_query = count_query.join(Player).where(Player.full_name.ilike(f"%{search}%"))
    if team_id:
        count_query = count_query.join(Player).where(Player.team_id == team_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Get paginated results
    query = query.order_by(PlayerSeasonStats.season.desc(), PlayerSeasonStats.player_id).offset(offset).limit(limit)
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
        "total": total,
        "offset": offset,
        "limit": limit,
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
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db)
):
    """List games with pagination."""
    query = (
        select(Game)
        .options(selectinload(Game.home_team), selectinload(Game.away_team))
    )
    
    if team_id:
        query = query.where((Game.home_team_id == team_id) | (Game.away_team_id == team_id))
    if season:
        query = query.where(Game.season == season)
    if status:
        query = query.where(Game.status == status)
    
    # Get total count
    count_query = select(func.count(Game.id))
    if team_id:
        count_query = count_query.where((Game.home_team_id == team_id) | (Game.away_team_id == team_id))
    if season:
        count_query = count_query.where(Game.season == season)
    if status:
        count_query = count_query.where(Game.status == status)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Get paginated results
    query = query.order_by(Game.start_time_utc.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    games = result.scalars().all()
    
    # Convert UTC to Eastern Time for display
    eastern = zoneinfo.ZoneInfo("America/New_York")
    
    games_list = []
    for g in games:
        if g.start_time_utc:
            utc_time = g.start_time_utc.replace(tzinfo=timezone.utc)
            eastern_time = utc_time.astimezone(eastern)
            game_date = eastern_time.strftime("%Y-%m-%d")
            game_time = eastern_time.strftime("%H:%M")
        else:
            game_date = None
            game_time = None
        
        games_list.append({
            "id": g.id,
            "nba_game_id": g.nba_game_id,
            "home_team": g.home_team.abbreviation if g.home_team else None,
            "away_team": g.away_team.abbreviation if g.away_team else None,
            "home_team_id": g.home_team_id,
            "away_team_id": g.away_team_id,
            "home_score": g.home_score,
            "away_score": g.away_score,
            "status": g.status,
            "game_date": game_date,
            "game_time": game_time,
            "season": g.season,
        })
    
    return {
        "games": games_list,
        "count": len(games),
        "total": total,
        "offset": offset,
        "limit": limit,
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


# ============ Player Game Stats ============

class PlayerGameStatsCreate(BaseModel):
    player_id: int
    game_id: int
    pts: int = 0
    reb: int = 0
    ast: int = 0
    stl: int = 0
    blk: int = 0
    minutes: Optional[str] = None


class PlayerGameStatsUpdate(BaseModel):
    pts: Optional[int] = None
    reb: Optional[int] = None
    ast: Optional[int] = None
    stl: Optional[int] = None
    blk: Optional[int] = None
    minutes: Optional[str] = None


@router.get("/player-game-stats")
async def list_player_game_stats(
    player_id: Optional[int] = None,
    game_id: Optional[int] = None,
    search: Optional[str] = Query(default=None),
    team_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db)
):
    """List player game stats with search and pagination."""
    try:
        # Build base query with proper relationship loading
        from sqlalchemy.orm import joinedload
        query = (
            select(PlayerGameStats)
            .options(
                selectinload(PlayerGameStats.player),
                joinedload(PlayerGameStats.game).joinedload(Game.home_team),
                joinedload(PlayerGameStats.game).joinedload(Game.away_team)
            )
        )
        
        # Apply filters
        if player_id:
            query = query.where(PlayerGameStats.player_id == player_id)
        if game_id:
            query = query.where(PlayerGameStats.game_id == game_id)
        if search:
            # Use a subquery to filter by player name
            player_subq = select(Player.id).where(Player.full_name.ilike(f"%{search}%"))
            query = query.where(PlayerGameStats.player_id.in_(player_subq))
        if team_id:
            # Filter by player's team
            player_subq = select(Player.id).where(Player.team_id == team_id)
            query = query.where(PlayerGameStats.player_id.in_(player_subq))
        
        # Get total count (simpler query without joins for count)
        count_query = select(func.count(PlayerGameStats.id))
        if player_id:
            count_query = count_query.where(PlayerGameStats.player_id == player_id)
        if game_id:
            count_query = count_query.where(PlayerGameStats.game_id == game_id)
        if search:
            player_subq = select(Player.id).where(Player.full_name.ilike(f"%{search}%"))
            count_query = count_query.where(PlayerGameStats.player_id.in_(player_subq))
        if team_id:
            player_subq = select(Player.id).where(Player.team_id == team_id)
            count_query = count_query.where(PlayerGameStats.player_id.in_(player_subq))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # Get paginated results
        query = query.order_by(PlayerGameStats.id.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        stats = result.unique().scalars().all()
        
        return {
            "stats": [
                {
                    "id": s.id,
                    "player_id": s.player_id,
                    "player_name": s.player.full_name if s.player else None,
                    "game_id": s.game_id,
                    "game_date": s.game.start_time_utc.strftime("%Y-%m-%d") if s.game and s.game.start_time_utc else None,
                    "home_team": s.game.home_team.abbreviation if s.game and s.game.home_team else None,
                    "away_team": s.game.away_team.abbreviation if s.game and s.game.away_team else None,
                    "pts": s.pts,
                    "reb": s.reb,
                    "ast": s.ast,
                    "stl": s.stl,
                    "blk": s.blk,
                    "minutes": s.minutes,
                }
                for s in stats
            ],
            "count": len(stats),
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except Exception as e:
        print(f"Error in list_player_game_stats: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching game stats: {str(e)}")


@router.post("/player-game-stats")
async def create_player_game_stats(
    data: PlayerGameStatsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create player game stats."""
    # Check if stats already exist
    result = await db.execute(
        select(PlayerGameStats).where(
            PlayerGameStats.player_id == data.player_id,
            PlayerGameStats.game_id == data.game_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Stats for this player/game already exist")
    
    stats = PlayerGameStats(
        player_id=data.player_id,
        game_id=data.game_id,
        pts=data.pts,
        reb=data.reb,
        ast=data.ast,
        stl=data.stl,
        blk=data.blk,
        minutes=data.minutes,
        source="manual",
        created_at=datetime.utcnow(),
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)
    
    return {"id": stats.id, "message": "Game stats created"}


@router.put("/player-game-stats/{stats_id}")
async def update_player_game_stats(
    stats_id: int,
    data: PlayerGameStatsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update player game stats."""
    result = await db.execute(select(PlayerGameStats).where(PlayerGameStats.id == stats_id))
    stats = result.scalar_one_or_none()
    
    if not stats:
        raise HTTPException(status_code=404, detail="Game stats not found")
    
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
    if data.minutes is not None:
        stats.minutes = data.minutes
    
    stats.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"id": stats.id, "message": "Game stats updated"}


@router.delete("/player-game-stats/{stats_id}")
async def delete_player_game_stats(
    stats_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete player game stats."""
    result = await db.execute(select(PlayerGameStats).where(PlayerGameStats.id == stats_id))
    stats = result.scalar_one_or_none()
    
    if not stats:
        raise HTTPException(status_code=404, detail="Game stats not found")
    
    await db.delete(stats)
    await db.commit()
    
    return {"message": "Game stats deleted"}


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
