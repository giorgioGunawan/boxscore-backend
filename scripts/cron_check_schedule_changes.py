#!/usr/bin/env python3
"""
Standalone script to check for schedule changes.
Can be run as a Render Cron Job or manually.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.services.cron_service import CronService
from app.models.cron_job import CronRun
from datetime import datetime, timezone


async def main():
    """Run the check_schedule_changes job standalone."""
    print(f"🚀 Starting check_schedule_changes")
    print(f"⏰ Current time: {datetime.now(timezone.utc).isoformat()}")
    
    async with AsyncSessionLocal() as db:
        # Create a CronRun record for tracking
        run = CronRun(
            job_id=3,  # Assuming job_id 3 is check_schedule_changes
            job_name="check_schedule_changes",
            started_at=datetime.now(timezone.utc),
            status="running",
            triggered_by="cron",
            details={"logs": [], "errors": []}
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        
        try:
            # Run the job
            result = await CronService.check_schedule_changes(
                run_id=run.id,
                cancellation_token=None
            )
            
            print("\n✅ Job completed successfully!")
            print(f"📊 Items updated: {result.get('items_updated', 0)}")
            print(f"⏱️  Duration: {result.get('details', {}).get('duration_seconds', 0):.2f}s")
            
            # Print summary logs
            logs = result.get('details', {}).get('logs', [])
            if logs:
                print("\n📋 Summary:")
                for log in logs[-10:]:  # Last 10 logs
                    print(f"   {log}")
            
            return 0
            
        except Exception as e:
            print(f"\n❌ Job failed: {str(e)}")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

