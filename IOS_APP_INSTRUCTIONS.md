# iOS App Development Instructions - NBA Boxscore Widgets

## Overview

You are building an iOS app that displays NBA data using widgets. The backend API is hosted at **https://boxscore-backend.onrender.com/** and provides all the necessary endpoints for displaying NBA team and player information.

## Base URL

```
https://boxscore-backend.onrender.com
```

All API endpoints are prefixed with `/api/`. The API returns JSON responses.

## Rate Limiting (Throttling)

To prevent abuse, the API has rate limits (throttling) enabling fair usage.

### Limits
- **Public Endpoints**: 100 requests per minute.
- **Player Search**: 20 requests per minute.

### Handling Limits
1. **Status Code**: If you exceed the limit, the API returns `429 Too Many Requests`.
2. **Retry**: You should handle this by waiting a minute before retrying.

### Best Practice: Device ID
Rate limits are applied per IP address by default. To prevent rate limiting purely based on public IP (e.g. users on the same Wi-Fi), **you should send a unique Device ID**.

Add the `X-Device-ID` header to all your requested:
```swift
var request = URLRequest(url: url)
request.addValue(UIDevice.current.identifierForVendor?.uuidString ?? "unknown", forHTTPHeaderField: "X-Device-ID")
```

## Critical: ID Mapping System

### Team ID Mapping

**IMPORTANT**: The backend uses **internal team IDs** (integers like 1, 2, 3...) for team endpoints, NOT NBA team IDs or abbreviations. You MUST map team abbreviations (like "GSW", "LAL", "BOS") to internal team IDs.

**How to get Team ID mapping:**

1. **Call `/api/teams`** to get all teams with their internal IDs:
   ```
   GET https://boxscore-backend.onrender.com/api/teams
   ```

2. **Response format:**
   ```json
   {
     "teams": [
       {
         "id": 2,
         "nba_team_id": 1610612744,
         "name": "Golden State Warriors",
         "abbreviation": "GSW",
         "conference": "West",
         "division": "Pacific"
       },
       ...
     ],
     "count": 30
   }
   ```

3. **Store this mapping** in your iOS app (e.g., UserDefaults, CoreData, or a static dictionary). The `id` field is what you use for all team-related endpoints.

4. **Team information can change** (trades, etc.), so periodically refresh this mapping by calling `/api/teams` again.

**Alternative**: You can also get a team by abbreviation:
```
GET /api/teams/abbr/{abbreviation}
```
Example: `/api/teams/abbr/GSW` returns the team object with the internal `id`.

### Player ID Mapping

**IMPORTANT**: The backend uses **NBA Player IDs** (integers like 201939, 2544, 1628369) for player endpoints. These are consistent across NBA systems.

**Player Database File:**

A `players_db.json` file is provided with player information. This file contains:
- `nba_player_id`: The NBA player ID to use in API calls
- `name`: Player's full name
- `team`: Current team abbreviation (e.g., "GSW", "LAL")
- `team_name`: Full team name
- `number`: Jersey number
- `position`: Position (G, F, C, etc.)
- Other metadata (height, weight, age, etc.)

**Important Notes:**
- **DO NOT hardcode team information from players_db.json**. The `team` field in the JSON may be outdated due to trades.
- **Always fetch current team information** from the API using `/api/teams` or `/api/players/{nba_player_id}/info`.
- Use `players_db.json` primarily for:
  - Player name → NBA Player ID lookup
  - Initial player discovery
  - Displaying player metadata (jersey number, position, etc.)

**Getting current team for a player:**

```
GET /api/players/{nba_player_id}/info
```

Response includes `team_id` (internal team ID) which you can use with team endpoints.

## Widget Endpoints

The app should implement 6 widgets as shown in the admin dashboard's "Widgets" tab. Here are the endpoints for each:

### Widget 1: Next 3 Games

**Endpoint:**
```
GET /api/teams/{team_id}/next-games?count=3
```

**Additional endpoint for team record:**
```
GET /api/teams/{team_id}/standings
```

**Response format:**
```json
{
  "team_id": 2,
  "games": [
    {
      "game_id": 123,
      "nba_game_id": "0022500364",
      "date": "2025-12-09",
      "time": "00:00",
      "datetime_utc": "2025-12-09T00:00:00+00:00",
      "opponent": "SAC",
      "opponent_name": "Sacramento Kings",
      "is_home": true,
      "venue": "Home"
    },
    ...
  ],
  "count": 3
}
```

**Standings response:**
```json
{
  "team_id": 2,
  "team_name": "Golden State Warriors",
  "abbreviation": "GSW",
  "conference": "West",
  "wins": 11,
  "losses": 11,
  "conference_rank": 9,
  "streak": "W2"
}
```

**Display format:**
- Show team record: "GSW (11-11)"
- For each game: "vs LAL (11-10) 8 Dec 8:30PM"
- **IMPORTANT**: Times are in UTC. Convert `datetime_utc` to user's local timezone for display.

### Widget 2: Season Average

**Endpoint:**
```
GET /api/players/{nba_player_id}/season-averages
```

**Example:** `/api/players/201939/season-averages` (Stephen Curry)

**Response format:**
```json
{
  "player_id": 1,
  "nba_player_id": 201939,
  "player_name": "Stephen Curry",
  "jersey_number": 30,
  "season": "2025-26",
  "pts": 28.5,
  "reb": 5.2,
  "ast": 6.8,
  "stl": 1.2,
  "blk": 0.3,
  "fg_pct": 0.45,
  "fg3_pct": 0.40,
  "ft_pct": 0.90,
  "games_played": 22,
  "minutes": 34.5
}
```

**Display format:**
- Player name and jersey: "Steph Curry | 30"
- Stats: "30ppg 15apg 12rpg 1bpg 1spg"
- Percentages: "45%fg 40%3fg 90%ft"

### Widget 3: Team's Last 3 Results

**Endpoint:**
```
GET /api/teams/{team_id}/last-games?count=3
```

**Response format:**
```json
{
  "team_id": 2,
  "games": [
    {
      "game_id": 120,
      "nba_game_id": "0022500300",
      "date": "2025-12-05",
      "datetime_utc": "2025-12-05T03:00:00+00:00",
      "opponent": "LAL",
      "opponent_name": "Los Angeles Lakers",
      "is_home": false,
      "team_score": 108,
      "opponent_score": 102,
      "result": "W",
      "score_display": "108-102"
    },
    ...
  ],
  "count": 3
}
```

**Display format:**
- For each game: "GSW vs LAL 108 - 102" (with win/loss indicator)
- Date: "5 Dec"

### Widget 4: Team Standing

**Endpoint:**
```
GET /api/teams/{team_id}/standings
```

**Response format:** (Same as Widget 1 standings)

**Display format:**
- Team name and record: "Golden State Warriors (11-11)"
- Conference rank: "9th in West"

### Widget 5: Player Last Game

**Endpoint:**
```
GET /api/players/{nba_player_id}/latest-game
```

**Example:** `/api/players/201939/latest-game` (Stephen Curry)

**Response format:**
```json
{
  "player_id": 1,
  "player_name": "Stephen Curry",
  "jersey_number": 30,
  "season": "2025-26",
  "game_date": "05 Dec 2025",
  "datetime_utc": "2025-12-05T03:00:00+00:00",
  "opponent": "LAL",
  "is_home": false,
  "pts": 30,
  "reb": 15,
  "ast": 4,
  "stl": 2,
  "blk": 1,
  "fg_pct": 0.45,
  "fg3_pct": 0.40,
  "ft_pct": 0.90
}
```

**Display format:**
- "Steph Curry — 5 Dec - 30 PTS, 15 REB, 4 AST vs LAL"

### Widget 6: Countdown to Next Game

**Endpoint:**
```
GET /api/teams/{team_id}/next-games?count=1
```

**Response format:** (Same as Widget 1, but only 1 game)

**Display format:**
- Calculate time until game start from `datetime_utc`
- Show countdown: "Next game in 2h 15m" or "Game starts at 8:30PM"

## Timezone Handling

**CRITICAL**: All game times (`datetime_utc`) are returned in **UTC**. You MUST:

1. Parse the UTC datetime string (ISO 8601 format: `2025-12-09T00:00:00+00:00`)
2. Convert to user's local timezone for display
3. Use iOS `DateFormatter` with appropriate timezone settings

**Example Swift code:**
```swift
let formatter = ISO8601DateFormatter()
formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
if let date = formatter.date(from: datetimeUtcString) {
    let localFormatter = DateFormatter()
    localFormatter.timeZone = TimeZone.current
    localFormatter.dateStyle = .medium
    localFormatter.timeStyle = .short
    let localTimeString = localFormatter.string(from: date)
}
```

## Error Handling

The API may return errors or empty data. Handle these cases gracefully:

1. **Network errors**: Show appropriate error messages
2. **Empty responses**: Some endpoints return `{"games": [], "count": 0}` - handle gracefully
3. **404 errors**: Player/team not found - show user-friendly message
4. **503 errors**: NBA API temporarily unavailable - show retry option

## API Response Patterns

### Success Response
Most endpoints return JSON with data:
```json
{
  "team_id": 2,
  "games": [...],
  "count": 3
}
```

### Error Response
Some endpoints return error in response body:
```json
{
  "team_id": 2,
  "games": [],
  "count": 0,
  "error": "Data temporarily unavailable"
}
```

### HTTP Status Codes
- `200`: Success
- `404`: Not found (team/player doesn't exist)
- `503`: Service unavailable (NBA API down)

## Implementation Checklist

1. ✅ **Initialize Team ID Mapping**
   - Call `/api/teams` on app launch
   - Store mapping (abbreviation → internal ID) in app
   - Refresh periodically (daily or on app launch)

2. ✅ **Load Player Database**
   - Parse `players_db.json` file
   - Create lookup: player name → NBA Player ID
   - Use for player search/selection UI

3. ✅ **Implement Widget 1: Next 3 Games**
   - Use team internal ID
   - Fetch next games + standings
   - Convert UTC times to local
   - Display with opponent records

4. ✅ **Implement Widget 2: Season Average**
   - Use NBA Player ID
   - Display stats with formatting

5. ✅ **Implement Widget 3: Last 3 Results**
   - Use team internal ID
   - Display win/loss indicators
   - Show scores

6. ✅ **Implement Widget 4: Team Standing**
   - Use team internal ID
   - Display record and conference rank

7. ✅ **Implement Widget 5: Player Last Game**
   - Use NBA Player ID
   - Display formatted stats

8. ✅ **Implement Widget 6: Countdown**
   - Use team internal ID
   - Calculate time until next game
   - Update countdown timer

9. ✅ **Timezone Conversion**
   - All `datetime_utc` fields → convert to local time
   - Use iOS date/time formatters

10. ✅ **Error Handling**
    - Network errors
    - Empty data
    - API errors

## Example API Calls

### Get all teams (for ID mapping)
```swift
let url = URL(string: "https://boxscore-backend.onrender.com/api/teams")!
// Parse response and store team ID mapping
```

### Get next games for GSW (team_id = 2)
```swift
let url = URL(string: "https://boxscore-backend.onrender.com/api/teams/2/next-games?count=3")!
```

### Get Stephen Curry's season averages (nba_player_id = 201939)
```swift
let url = URL(string: "https://boxscore-backend.onrender.com/api/players/201939/season-averages")!
```

### Get team by abbreviation
```swift
let url = URL(string: "https://boxscore-backend.onrender.com/api/teams/abbr/GSW")!
```

## Testing

Test the API endpoints using:
- Browser: Visit `https://boxscore-backend.onrender.com/docs` for interactive API docs
- Admin Dashboard: Visit `https://boxscore-backend.onrender.com/api/admin/` and use the "Widgets" tab to see example responses

## Notes

- The backend auto-creates player records on first API call, so you don't need to register players
- Team information (including which team a player is on) should be fetched from the API, not hardcoded
- All times are in UTC - always convert to user's local timezone
- The API uses caching, so responses may be slightly delayed but are more reliable
- Some endpoints support a `refresh=true` query parameter to force fresh data from NBA API


