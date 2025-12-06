#!/usr/bin/env python3
"""
Database migration script for production deployments.

Usage:
    python scripts/migrate.py              # Run all pending migrations
    python scripts/migrate.py --status     # Check migration status
    python scripts/migrate.py --rollback   # Rollback last migration
    python scripts/migrate.py --reset      # Reset and recreate all tables (DANGER!)
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, init_db, Base
from app.models import *  # Import all models


async def check_tables():
    """Check which tables exist."""
    async with engine.connect() as conn:
        # For SQLite
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result.fetchall()]
        return tables


async def run_migrations():
    """Run database migrations (create all tables)."""
    print("🔄 Running database migrations...")
    
    # Check existing tables
    existing = await check_tables()
    print(f"   Existing tables: {existing}")
    
    # Create all tables
    await init_db()
    
    # Check new tables
    new_tables = await check_tables()
    created = set(new_tables) - set(existing)
    
    if created:
        print(f"✅ Created tables: {created}")
    else:
        print("✅ All tables already exist")
    
    print(f"   Total tables: {len(new_tables)}")


async def check_status():
    """Check migration status."""
    print("📊 Database Status")
    print("=" * 40)
    
    tables = await check_tables()
    print(f"Tables in database ({len(tables)}):")
    for table in sorted(tables):
        print(f"  - {table}")
    
    # Check for new columns (source tracking)
    async with engine.connect() as conn:
        for table in ['teams', 'players', 'games', 'player_season_stats', 'team_standings', 'player_game_stats']:
            if table in tables:
                try:
                    result = await conn.execute(text(f"PRAGMA table_info({table})"))
                    columns = [row[1] for row in result.fetchall()]
                    has_source = 'source' in columns
                    has_override = 'is_manual_override' in columns
                    status = "✅" if (has_source and has_override) else "⚠️ needs migration"
                    print(f"  {table}: {status}")
                except Exception as e:
                    print(f"  {table}: ❌ error - {e}")


async def reset_database():
    """Reset database (drop and recreate all tables)."""
    print("⚠️  WARNING: This will DELETE all data!")
    confirm = input("Type 'RESET' to confirm: ")
    
    if confirm != 'RESET':
        print("Cancelled.")
        return
    
    print("🗑️  Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("🔄 Recreating tables...")
    await init_db()
    
    print("✅ Database reset complete")


async def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--status':
            await check_status()
        elif arg == '--reset':
            await reset_database()
        elif arg == '--rollback':
            print("⚠️  Rollback not implemented. Use --reset for full reset.")
        else:
            print(f"Unknown argument: {arg}")
            print(__doc__)
    else:
        await run_migrations()


if __name__ == "__main__":
    asyncio.run(main())

