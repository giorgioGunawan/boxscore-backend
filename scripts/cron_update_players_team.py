#!/usr/bin/env python3
"""
Standalone script to update players' team assignments.
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
    """Run the update_players_team job standalone."""
    print(f"🚀 Starting update_players_team")
    print(f"⏰ Current time: {datetime.now(timezone.utc).isoformat()}")
    
    async with AsyncSessionLocal() as db:
        # Create a CronRun record for tracking
        run = CronRun(
            job_id=4,  # Assuming job_id 4 is update_players_team
            job_name="update_players_team",
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
            result = await CronService.update_players_team(
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
                for log in logs[-15:]:  # Last 15 logs
                    print(f"   {log}")
            
            return 0
            
        except Exception as e:
            print(f"\n❌ Job failed: {str(e)}")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

