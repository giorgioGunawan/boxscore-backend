#!/usr/bin/env python3
"""
Export database data to JSON for backup or migration.

Usage:
    python scripts/export_data.py                    # Export all data
    python scripts/export_data.py --table players    # Export specific table
    python scripts/export_data.py --overrides-only   # Export only manual overrides
"""

import asyncio
import json
import sys
import os
from datetime import datetime, date, time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import Team, Player, Game, PlayerSeasonStats, TeamStandings, PlayerGameStats


def serialize_value(v):
    """Serialize a value for JSON."""
    if isinstance(v, datetime):
        return v.isoformat()
    elif isinstance(v, date):
        return v.isoformat()
    elif isinstance(v, time):
        return v.isoformat()
    return v


def model_to_dict(obj):
    """Convert SQLAlchemy model to dict."""
    return {
        c.name: serialize_value(getattr(obj, c.name))
        for c in obj.__table__.columns
    }


async def export_table(session, model_class, overrides_only=False):
    """Export a single table."""
    query = select(model_class)
    
    if overrides_only and hasattr(model_class, 'is_manual_override'):
        query = query.where(model_class.is_manual_override == True)
    
    result = await session.execute(query)
    records = result.scalars().all()
    
    return [model_to_dict(r) for r in records]


async def export_all(overrides_only=False):
    """Export all tables."""
    await init_db()
    
    async with AsyncSessionLocal() as session:
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "overrides_only": overrides_only,
            "tables": {}
        }
        
        tables = [
            ("teams", Team),
            ("players", Player),
            ("games", Game),
            ("player_season_stats", PlayerSeasonStats),
            ("team_standings", TeamStandings),
            ("player_game_stats", PlayerGameStats),
        ]
        
        for table_name, model_class in tables:
            print(f"Exporting {table_name}...")
            records = await export_table(session, model_class, overrides_only)
            data["tables"][table_name] = records
            print(f"  - {len(records)} records")
        
        return data


async def main():
    overrides_only = '--overrides-only' in sys.argv
    specific_table = None
    
    for i, arg in enumerate(sys.argv):
        if arg == '--table' and i + 1 < len(sys.argv):
            specific_table = sys.argv[i + 1]
    
    data = await export_all(overrides_only)
    
    # Generate filename
    suffix = "_overrides" if overrides_only else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup{suffix}_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Exported to {filename}")
    print(f"   Total records: {sum(len(v) for v in data['tables'].values())}")


if __name__ == "__main__":
    asyncio.run(main())

