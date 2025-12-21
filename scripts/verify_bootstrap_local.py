import asyncio
import os
import sys
from sqlalchemy import text

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override settings before importing other modules if needed, 
# but env var works best with BaseSettings
# WE MUST set this before importing app.config if we were modifying the object directly,
# but since it reads env vars on instantiation and get_settings is cached, 
# we rely on the process env var passing.

from app.database import init_db, AsyncSessionLocal
from app.services.cron_service import CronService

async def main():
    db_url = os.environ.get('DATABASE_URL')
    print(f"🧪 Using test database: {db_url}")
    
    # Initialize DB (creates tables in the new db file)
    print("🔨 Initializing database schema...")
    await init_db()
    
    # Run bootstrap
    print("🚀 Starting bootstrap_database (this may take 30-60s)...")
    # We pass a dummy run_id. In a real scenario, this would exist in the DB.
    # update_run_progress might fail if run_id doesn't exist in cron_runs table?
    # Let's check update_run_progress implementation.
    # It likely updates a record. If it fails, we might need to insert a dummy run first.
    # However, for now let's try.
    
    try:
        # We need to insert a dummy cron_run because update_run_progress will try to update it
        async with AsyncSessionLocal() as db:
             await db.execute(text("INSERT INTO cron_runs (id, job_id, job_name, status, started_at) VALUES (999, 0, 'bootstrap_test', 'running', CURRENT_TIMESTAMP)"))
             await db.commit()
    except Exception as e:
        print(f"⚠️ Could not insert dummy run (might already exist or schema issue): {e}")

    result = await CronService.bootstrap_database(run_id=999)
    
    print("\n📊 Bootstrap Result:")
    import json
    print(json.dumps(result, indent=2, default=str))
    
    if result["status"] == "success":
        async with AsyncSessionLocal() as db:
            team_count = await db.execute(text("SELECT COUNT(*) FROM teams"))
            game_count = await db.execute(text("SELECT COUNT(*) FROM games"))
            player_count = await db.execute(text("SELECT COUNT(*) FROM players"))
            
            print(f"\n✅ Verification Counts:")
            print(f"   Teams: {team_count.scalar()}")
            print(f"   Games: {game_count.scalar()}")
            print(f"   Players: {player_count.scalar()}")
    else:
        print("\n❌ Bootstrap failed.")

if __name__ == "__main__":
    asyncio.run(main())
