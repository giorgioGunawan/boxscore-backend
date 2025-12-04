# NBA Boxscore Backend

A Python backend for NBA widget data - schedules, standings, and player stats. Built with FastAPI, PostgreSQL, and Redis caching.

## Features

- **Team Data**: All 30 NBA teams with conference/division info
- **Game Schedules**: Next N and last N games for any team
- **Standings**: Conference standings with ranks, records, streaks
- **Player Stats**: Season averages (PPG, RPG, APG, SPG, BPG)
- **Player Game Logs**: Latest game stats for any player
- **Caching**: Redis cache-aside pattern for all endpoints
- **Admin Console**: Web UI for data management and monitoring

## API Endpoints

### Teams
```
GET  /api/teams                           # List all teams
GET  /api/teams/{id}                      # Get team by ID
GET  /api/teams/abbr/{abbr}               # Get team by abbreviation (GSW, LAL, etc.)
GET  /api/teams/{id}/next-games?count=5   # Next N upcoming games
GET  /api/teams/{id}/last-games?count=5   # Last N completed games
GET  /api/teams/{id}/standings            # Team standings
GET  /api/teams/standings/{conference}    # Full conference standings (East/West)
```

### Players
```
GET  /api/players/search?name=curry       # Search players by name
GET  /api/players/{id}                    # Get player by internal ID
GET  /api/players/nba/{nba_id}            # Get player by NBA.com ID
GET  /api/players/{id}/season-averages    # Season stats (PPG, RPG, APG, etc.)
GET  /api/players/{id}/latest-game        # Most recent game stats
POST /api/players/register/{nba_id}       # Register a player in the system
```

### Admin
```
GET  /api/admin/                          # Admin dashboard UI
GET  /api/admin/metrics                   # Cache metrics
GET  /api/admin/stats                     # Database statistics
POST /api/admin/refresh/teams             # Seed/refresh teams
POST /api/admin/refresh/standings         # Refresh all standings
POST /api/admin/refresh/team/{id}/games   # Refresh team's games
POST /api/admin/cache/clear?pattern=*     # Clear cache
GET  /api/admin/teams/{id}/inspect        # Inspect team data
GET  /api/admin/players/{id}/inspect      # Inspect player data
```

## Quick Start

### With Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

The API will be available at `http://localhost:8000`

### Local Development

1. **Install dependencies**
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. **Start PostgreSQL and Redis**
```bash
# Using Docker
docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=boxscore_nba postgres:15-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run the server**
```bash
uvicorn app.main:app --reload
```

## Configuration

Environment variables (set in `.env` or environment):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CURRENT_SEASON` | `2024-25` | NBA season to fetch data for |
| `CACHE_TTL_GAMES` | `3600` | Cache TTL for games (seconds) |
| `CACHE_TTL_STANDINGS` | `1800` | Cache TTL for standings |
| `CACHE_TTL_PLAYER_STATS` | `3600` | Cache TTL for player stats |
| `CACHE_TTL_PLAYER_GAME` | `900` | Cache TTL for player game logs |

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI   │────▶│    Redis    │
│  (Widget)   │◀────│   Backend   │◀────│   Cache     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    Cache Miss?
                           │
                    ┌──────▼──────┐     ┌─────────────┐
                    │  PostgreSQL │◀───▶│   nba_api   │
                    │   Database  │     │  (NBA.com)  │
                    └─────────────┘     └─────────────┘
```

1. Client requests data from the API
2. Check Redis cache for cached response
3. If cache hit, return cached data
4. If cache miss, check PostgreSQL database
5. If data is stale or missing, fetch from NBA API via `nba_api`
6. Store in PostgreSQL and cache in Redis
7. Return response to client

## Widget Examples

### Next Games Widget
```json
GET /api/teams/1/next-games?count=3

{
  "team_id": 1,
  "games": [
    {
      "date": "2024-12-05",
      "time": "19:30",
      "opponent": "LAL",
      "opponent_name": "Los Angeles Lakers",
      "is_home": true,
      "venue": "Home"
    }
  ]
}
```

### Player Season Averages
```json
GET /api/players/1/season-averages

{
  "player_id": 1,
  "player_name": "Stephen Curry",
  "season": "2024-25",
  "ppg": 23.5,
  "rpg": 4.2,
  "apg": 6.1,
  "spg": 1.2,
  "bpg": 0.3
}
```

### Team Standings
```json
GET /api/teams/1/standings

{
  "team_id": 1,
  "team_name": "Golden State Warriors",
  "record": "11-11",
  "conference_rank": 9,
  "conference_rank_display": "9th",
  "conference": "West",
  "streak": "W2"
}
```

## Admin Console

Access the admin console at `/api/admin/` to:

- View database statistics
- Monitor cache hit rates
- Trigger manual data refreshes
- Inspect team/player data
- Clear cache entries

## Development

### Database Migrations

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Project Structure

```
boxscore-backend/
├── app/
│   ├── api/              # API route handlers
│   │   ├── admin.py      # Admin endpoints
│   │   ├── players.py    # Player endpoints
│   │   └── teams.py      # Team endpoints
│   ├── models/           # SQLAlchemy models
│   ├── nba_client/       # NBA API wrapper
│   ├── services/         # Business logic
│   ├── templates/        # Jinja2 templates
│   ├── cache.py          # Redis caching
│   ├── config.py         # Settings
│   ├── database.py       # Database setup
│   └── main.py           # FastAPI app
├── alembic/              # Database migrations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## License

MIT

