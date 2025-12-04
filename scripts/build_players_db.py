#!/usr/bin/env python3
"""
Build a players database JSON file from all NBA team rosters.
This creates a players_db.json file with all players and their info.
"""
import json
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.nba_client import NBAClient
from app.config import get_settings

settings = get_settings()


def build_players_db():
    """Fetch all team rosters and build a players database."""
    print(f"🏀 Building players database for season {settings.current_season}...")
    
    # Get all teams
    teams = NBAClient.get_all_teams()
    print(f"📋 Found {len(teams)} teams")
    
    all_players = []
    players_by_id = {}  # To track duplicates
    
    for i, team in enumerate(teams, 1):
        team_id = team["nba_team_id"]
        team_name = team["name"]
        team_abbr = team["abbreviation"]
        
        print(f"  [{i:2}/{len(teams)}] Fetching {team_name} ({team_abbr})...", end=" ", flush=True)
        
        try:
            roster = NBAClient.get_team_roster(team_id, season=settings.current_season)
            
            for player in roster:
                player_id = player["nba_player_id"]
                
                # Skip if we already have this player (traded players appear on multiple rosters)
                if player_id in players_by_id:
                    continue
                
                player_entry = {
                    "nba_player_id": player_id,
                    "name": player["name"],
                    "team": team_abbr,
                    "team_name": team_name,
                    "number": player["number"],
                    "position": player["position"],
                    "height": player["height"],
                    "weight": player["weight"],
                    "age": player["age"],
                    "experience": player["experience"],
                    "school": player["school"],
                }
                
                all_players.append(player_entry)
                players_by_id[player_id] = player_entry
            
            print(f"✓ {len(roster)} players")
            
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Sort by name
    all_players.sort(key=lambda p: p["name"])
    
    # Build the final database
    db = {
        "season": settings.current_season,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "total_players": len(all_players),
        "players": all_players,
    }
    
    # Save to file
    output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "players_db.json")
    with open(output_file, "w") as f:
        json.dump(db, f, indent=2)
    
    print(f"\n✅ Saved {len(all_players)} players to {output_file}")
    
    # Print some stats
    print(f"\n📊 Stats:")
    print(f"   Total players: {len(all_players)}")
    
    # Top 10 players by experience
    experienced = sorted(all_players, key=lambda p: int(p["experience"]) if p["experience"] and p["experience"] != "R" else 0, reverse=True)[:10]
    print(f"\n   Most experienced players:")
    for p in experienced:
        print(f"      {p['name']} ({p['team']}) - {p['experience']} years")
    
    return db


if __name__ == "__main__":
    build_players_db()

