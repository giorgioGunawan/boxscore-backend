# NBA Boxscore Backend

A Python backend for NBA widget data - schedules, standings, and player stats. Built with FastAPI, SQLite/PostgreSQL, and Redis caching.

## Features

- **Team Data**: All 30 NBA teams with conference/division info
- **Game Schedules**: Next N and last N games for any team
- **Standings**: Conference standings with ranks, records, streaks
- **Player Stats**: Season averages (PPG, RPG, APG, SPG, BPG)
- **Player Game Logs**: Latest game stats for any player
- **Caching**: Redis cache-aside pattern (with in-memory fallback)
- **Admin Console**: Web UI for data management and monitoring
- **Hybrid Data Provider**: Local DB first, NBA API as fallback
- **Manual Overrides**: Full control over data when API is unavailable

## Architecture: Hybrid Data Provider

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR SWIFT APP                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR BACKEND API                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Router    │───▶│   Service   │───▶│   Data Provider     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                │                 │
│                          ┌─────────────────────┼─────────────┐  │
│                          ▼                     ▼             │  │
│                   ┌─────────────┐      ┌─────────────┐       │  │
│                   │  LOCAL DB   │      │  NBA API    │       │  │
│                   │  (Primary)  │      │ (Fallback)  │       │  │
│                   └─────────────┘      └─────────────┘       │  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Priority Logic

1. Check LOCAL DB for data
   - If EXISTS and FRESH (< TTL) → Return local data
   - If MANUAL OVERRIDE → Always return local data
   - If EXISTS but STALE → Try NBA API, fallback to local
   - If NOT EXISTS → Fetch from NBA API, store locally

2. If NBA API fails/unavailable
   - Return local data (even if stale) with "stale" flag

## API Endpoints

### Teams
```
GET  /api/teams                           # List all teams
GET  /api/teams/{id}                      # Get team by ID
GET  /api/teams/abbr/{abbr}               # Get team by abbreviation (GSW, LAL, etc.)
GET  /api/teams/{id}/next-games?count=5   # Next N upcoming games
GET  /api/teams/{id}/last-games?count=5   # Last N completed games
GET  /api/teams/{id}/standings            # Team standings
GET  /api/teams/{id}/roster               # Team roster
GET  /api/teams/standings/{conference}    # Full conference standings (East/West)
```

### Players
```
GET  /api/players/search?name=curry       # Search players by name
GET  /api/players/{nba_id}/info           # Get player info (auto-creates if needed)
GET  /api/players/{nba_id}/season-averages # Season stats (PPG, RPG, APG, etc.)
GET  /api/players/{nba_id}/latest-game    # Most recent game stats
```

### Admin Data Management
```
GET  /api/admin/data/overrides            # List all manual overrides
PUT  /api/admin/data/players/{id}         # Update player with manual data
PUT  /api/admin/data/players/{id}/season-stats/{season}  # Update player stats
PUT  /api/admin/data/games/{id}           # Update game score/status
POST /api/admin/data/games                # Create manual game
PUT  /api/admin/data/standings/{team_id}/{season}  # Update standings
DELETE /api/admin/data/players/{id}/override  # Clear override
POST /api/admin/data/sync-all             # Trigger full API sync
```

### Admin Console
```
GET  /api/admin/                          # Admin dashboard UI
GET  /api/admin/metrics                   # Cache metrics
GET  /api/admin/stats                     # Database statistics
POST /api/admin/refresh/teams             # Seed/refresh teams
POST /api/admin/refresh/standings         # Refresh all standings
POST /api/admin/cache/clear?pattern=*     # Clear cache
```

## Quick Start

### Local Development (Recommended)

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations (creates SQLite DB)
python scripts/migrate.py

# 4. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
Admin console at `http://localhost:8000/api/admin/`

### With Docker

```bash
docker-compose up -d
```

## Deployment to Render.com

### 1. Initial Setup

1. Create a new **Web Service** on Render
2. Connect your GitHub repository
3. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3.12

### 2. Environment Variables

Set these in Render dashboard:

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | `sqlite:///./boxscore.db` | Use SQLite for simplicity |
| `USE_REDIS` | `false` | Disable Redis (uses in-memory cache) |
| `CURRENT_SEASON` | `2025-26` | NBA season |

### 3. Database Migrations

**On first deploy**, the database is auto-initialized. For schema updates:

```bash
# SSH into your Render service or use the shell
python scripts/migrate.py --status  # Check current state
python scripts/migrate.py           # Run migrations
```

### 4. Data Backup & Restore

```bash
# Export data (run locally or on server)
python scripts/export_data.py

# Export only manual overrides
python scripts/export_data.py --overrides-only

# Import data
python scripts/import_data.py backup.json

# Import with merge (don't overwrite existing)
python scripts/import_data.py backup.json --merge
```

## Manual Data Management

The hybrid data provider allows you to:

1. **Override API data**: Set `is_manual_override=true` on any record
2. **Create manual entries**: Add games/stats that don't exist in NBA API
3. **Survive API outages**: Your local data persists even if NBA API goes down

### Via Admin Console

1. Go to `/api/admin/`
2. Click "Data Management" tab
3. Use the forms to:
   - Edit player stats
   - Edit game scores
   - Edit team standings
   - Create manual games

### Via API

```bash
# Override player stats
curl -X PUT http://localhost:8000/api/admin/data/players/1/season-stats/2025-26 \
  -H "Content-Type: application/json" \
  -d '{"pts": 30.5, "reb": 5.0, "ast": 6.5, "reason": "Corrected stats"}'

# Create manual game
curl -X POST http://localhost:8000/api/admin/data/games \
  -H "Content-Type: application/json" \
  -d '{
    "home_team_id": 1,
    "away_team_id": 2,
    "game_date": "2025-12-25",
    "game_time": "17:00",
    "season": "2025-26"
  }'
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./boxscore.db` | Database connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `USE_REDIS` | `false` | Enable Redis caching |
| `CURRENT_SEASON` | `2025-26` | NBA season |
| `CACHE_TTL_GAMES` | `3600` | Cache TTL for games (seconds) |
| `CACHE_TTL_STANDINGS` | `1800` | Cache TTL for standings |
| `CACHE_TTL_PLAYER_STATS` | `3600` | Cache TTL for player stats |
| `CACHE_TTL_PLAYER_GAME` | `900` | Cache TTL for player game logs |

## Project Structure

```
boxscore-backend/
├── app/
│   ├── api/              # API route handlers
│   │   ├── admin.py      # Admin endpoints
│   │   ├── admin_data.py # Data management endpoints
│   │   ├── players.py    # Player endpoints
│   │   └── teams.py      # Team endpoints
│   ├── models/           # SQLAlchemy models (with source tracking)
│   ├── nba_client/       # NBA API wrapper
│   ├── services/         # Business logic + data provider
│   ├── templates/        # Jinja2 templates (admin UI)
│   ├── cache.py          # Redis/in-memory caching
│   ├── config.py         # Settings
│   ├── database.py       # Database setup
│   └── main.py           # FastAPI app
├── scripts/
│   ├── migrate.py        # Database migrations
│   ├── export_data.py    # Data export
│   ├── import_data.py    # Data import
│   └── build_players_db.py # Generate players JSON
├── alembic/              # Alembic migrations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Common NBA Player IDs

| Player | NBA ID |
|--------|--------|
| Stephen Curry | 201939 |
| LeBron James | 2544 |
| Kevin Durant | 201142 |
| Jayson Tatum | 1628369 |
| Luka Dončić | 1629029 |
| Giannis Antetokounmpo | 203507 |
| Nikola Jokić | 203999 |
| Joel Embiid | 203954 |

## License

MIT
