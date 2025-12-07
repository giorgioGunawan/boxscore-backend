"""
Test script to run update_player_season_averages and check logs.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models import CronJob, CronRun, PlayerSeasonStats
from app.services.cron_service import CronService
from datetime import datetime, timezone, timedelta

async def test_job():
    """Test the update_player_season_averages job."""
    async with AsyncSessionLocal() as db:
        # First, set some players' last_api_sync to old date for testing
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        
        # Get first 5 players
        result = await db.execute(
            select(PlayerSeasonStats)
            .where(PlayerSeasonStats.season == '2025-26')
            .limit(5)
        )
        test_stats = result.scalars().all()
        
        if test_stats:
            print(f"📝 Setting {len(test_stats)} players' last_api_sync to old date for testing...")
            for stat in test_stats:
                stat.last_api_sync = old_date
            await db.commit()
            print("✅ Done!")
        
        # Get the cron job
        cron_job_result = await db.execute(
            select(CronJob).where(CronJob.name == "update_player_season_averages")
        )
        cron_job = cron_job_result.scalar_one_or_none()
        
        if not cron_job:
            print("❌ Cron job 'update_player_season_averages' not found!")
            return
        
        # Create a CronRun record
        cron_run = CronRun(
            job_id=cron_job.id,
            job_name="update_player_season_averages",
            started_at=datetime.now(timezone.utc),
            status="running",
            triggered_by="manual"
        )
        db.add(cron_run)
        await db.commit()
        await db.refresh(cron_run)
        
        print(f"\n✅ Created CronRun ID: {cron_run.id}")
        print(f"🔍 Running update_player_season_averages_batch...")
        print("=" * 60)
        
        # Run the job
        try:
            result = await CronService.update_player_season_averages_batch(
                run_id=cron_run.id,
                cancellation_token=None,
                batch_size=5  # Small batch for testing
            )
            
            print("\n" + "=" * 60)
            print("📊 RESULT:")
            print(f"   Status: {result.get('status', 'unknown')}")
            if 'items_updated' in result:
                print(f"   Items updated: {result['items_updated']}")
            if 'error' in result:
                print(f"   Error: {result['error']}")
            print(f"\n📋 LOGS:")
            if 'details' in result and 'logs' in result['details']:
                for log in result['details']['logs']:
                    print(f"   {log}")
            else:
                print("   No logs found!")
                if 'details' in result:
                    print(f"   Details keys: {list(result['details'].keys())}")
                
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_job())
