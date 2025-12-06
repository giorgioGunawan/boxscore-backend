#!/usr/bin/env python3
"""
Import database data from JSON backup.

Usage:
    python scripts/import_data.py backup.json              # Import all data
    python scripts/import_data.py backup.json --merge      # Merge with existing (don't overwrite)
    python scripts/import_data.py backup.json --overrides  # Only import overridden records
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import Team, Player, Game, PlayerSeasonStats, TeamStandings, PlayerGameStats


MODEL_MAP = {
    "teams": Team,
    "players": Player,
    "games": Game,
    "player_season_stats": PlayerSeasonStats,
    "team_standings": TeamStandings,
    "player_game_stats": PlayerGameStats,
}


def parse_datetime(value):
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except:
        return None


async def import_table(session, table_name, records, merge=False, overrides_only=False):
    """Import records into a table."""
    model_class = MODEL_MAP.get(table_name)
    if not model_class:
        print(f"  ⚠️  Unknown table: {table_name}")
        return 0
    
    imported = 0
    
    for record in records:
        # Filter to overrides only if requested
        if overrides_only and not record.get('is_manual_override'):
            continue
        
        # Check if record exists (by id)
        record_id = record.get('id')
        if record_id and merge:
            result = await session.execute(
                select(model_class).where(model_class.id == record_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                continue  # Skip existing records in merge mode
        
        # Create new record
        # Remove id to let database auto-generate
        record_data = {k: v for k, v in record.items() if k != 'id'}
        
        # Parse datetime fields
        for field in ['created_at', 'updated_at', 'last_api_sync', 'last_manual_edit', 'start_time_utc']:
            if field in record_data:
                record_data[field] = parse_datetime(record_data[field])
        
        try:
            obj = model_class(**record_data)
            session.add(obj)
            imported += 1
        except Exception as e:
            print(f"  ⚠️  Error importing record: {e}")
    
    await session.commit()
    return imported


async def import_all(filename, merge=False, overrides_only=False):
    """Import all tables from JSON file."""
    with open(filename, 'r') as f:
        data = json.load(f)
    
    print(f"📂 Loading from {filename}")
    print(f"   Exported at: {data.get('exported_at', 'unknown')}")
    print(f"   Mode: {'merge' if merge else 'replace'}")
    print(f"   Overrides only: {overrides_only}")
    print()
    
    await init_db()
    
    async with AsyncSessionLocal() as session:
        total_imported = 0
        
        # Import in dependency order
        table_order = ["teams", "players", "games", "player_season_stats", "team_standings", "player_game_stats"]
        
        for table_name in table_order:
            records = data.get("tables", {}).get(table_name, [])
            if records:
                print(f"Importing {table_name}...")
                count = await import_table(session, table_name, records, merge, overrides_only)
                print(f"  - Imported {count} records")
                total_imported += count
        
        print(f"\n✅ Import complete! Total: {total_imported} records")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    filename = sys.argv[1]
    merge = '--merge' in sys.argv
    overrides_only = '--overrides' in sys.argv
    
    if not os.path.exists(filename):
        print(f"❌ File not found: {filename}")
        sys.exit(1)
    
    await import_all(filename, merge, overrides_only)


if __name__ == "__main__":
    asyncio.run(main())

