"""
Test script to verify update_player_rosters is properly registered as a cron job.
"""
import asyncio
import sys
sys.path.insert(0, '/Users/giorgio/personal/boxscore-backend')

from app.database import AsyncSessionLocal
from app.cron.scheduler import initialize_cron_jobs
from app.models import CronJob
from sqlalchemy import select


async def test_cron_job_registration():
    """Test that update_player_rosters is registered."""
    print("🔍 Testing cron job registration...")
    print("=" * 60)
    
    # Initialize cron jobs (this will create/update them in the database)
    await initialize_cron_jobs()
    print("✅ Initialized cron jobs\n")
    
    # Check if update_player_rosters exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CronJob).where(CronJob.name == "update_player_rosters")
        )
        job = result.scalar_one_or_none()
        
        if job:
            print("✅ update_player_rosters job found!")
            print(f"   ID: {job.id}")
            print(f"   Name: {job.name}")
            print(f"   Description: {job.description}")
            print(f"   Schedule: {job.schedule}")
            print(f"   Is Active: {job.is_active}")
            print(f"   Total Runs: {job.total_runs}")
            print(f"   Successful Runs: {job.successful_runs}")
            print(f"   Failed Runs: {job.failed_runs}")
        else:
            print("❌ update_player_rosters job NOT found!")
            return False
        
        # List all manual jobs
        print("\n📋 All manual jobs:")
        result = await db.execute(
            select(CronJob).where(CronJob.schedule == "manual").order_by(CronJob.name)
        )
        manual_jobs = result.scalars().all()
        
        for j in manual_jobs:
            print(f"   • {j.name}: {j.description}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    return True


if __name__ == '__main__':
    success = asyncio.run(test_cron_job_registration())
    sys.exit(0 if success else 1)
