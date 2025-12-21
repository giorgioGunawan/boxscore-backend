"""Cron job scheduler using APScheduler."""
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import CronJob, CronRun
from app.services.cron_service import CronService
from app.config import get_settings
from app.cron.cancellation import get_cancellation_token, remove_token, cancel_run

settings = get_settings()

scheduler = AsyncIOScheduler()


async def run_job_now(job_name: str, job_func, *args, **kwargs):
    """Run a job immediately without checking cron_jobs table (for manual triggers)."""
    run_id = None
    cancellation_token = None
    
    print(f"[run_job_now] Starting job: {job_name}")
    
    try:
        async with AsyncSessionLocal() as db:
            # Create run record directly (no cron_jobs table lookup)
            run = CronRun(
                job_id=0,  # Not linked to a cron_job record
                job_name=job_name,
                triggered_by="manual",  # Manually triggered
                started_at=datetime.now(timezone.utc),
                status="running"
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id
            
            print(f"[run_job_now] Created CronRun record with ID: {run_id}")
            
            # Create cancellation token
            cancellation_token = get_cancellation_token(run_id)
        
        print(f"[run_job_now] Executing job function: {job_name}")
        
        # Execute the job with timeout (30 minutes max)
        timeout_seconds = 30 * 60
        result_data = await asyncio.wait_for(
            job_func(run_id, cancellation_token, *args, **kwargs),
            timeout=timeout_seconds
        )
        
        print(f"[run_job_now] Job {job_name} completed successfully")
        
        # Update run record
        async with AsyncSessionLocal() as db2:
            result2 = await db2.execute(
                select(CronRun).where(CronRun.id == run_id)
            )
            run2 = result2.scalar_one_or_none()
            if run2:
                run2.completed_at = datetime.now(timezone.utc)
                # Handle timezone-aware/naive datetime comparison
                if run2.started_at:
                    started = run2.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    run2.duration_seconds = int((run2.completed_at - started).total_seconds())
                else:
                    run2.duration_seconds = None
                run2.status = result_data.get("status", "success")
                run2.items_updated = result_data.get("items_updated", 0)
                
                # Merge details to preserve logs from update_run_progress
                existing_details = run2.details or {}
                new_details = result_data.get("details", {})
                # Merge: keep existing logs if they exist, otherwise use new logs
                merged_details = {**existing_details, **new_details}
                if "logs" in existing_details and "logs" in new_details:
                    # If both have logs, prefer existing (which has all the real-time logs)
                    merged_details["logs"] = existing_details["logs"]
                elif "logs" in existing_details:
                    # Keep existing logs
                    merged_details["logs"] = existing_details["logs"]
                elif "logs" in new_details:
                    # Use new logs if no existing logs
                    merged_details["logs"] = new_details["logs"]
                
                run2.details = merged_details
                
                if run2.status == "failed":
                    run2.error_message = result_data.get("error", "Unknown error")
                
                await db2.commit()
                print(f"[run_job_now] Updated run record {run_id} - status: {run2.status}, items: {run2.items_updated}")
    
    except asyncio.TimeoutError:
        print(f"[run_job_now] Job {job_name} timed out after {timeout_seconds} seconds")
        if run_id:
            async with AsyncSessionLocal() as db2:
                result2 = await db2.execute(
                    select(CronRun).where(CronRun.id == run_id)
                )
                run2 = result2.scalar_one_or_none()
                if run2:
                    run2.completed_at = datetime.now(timezone.utc)
                    run2.status = "failed"
                    run2.error_message = f"Job timed out after {timeout_seconds} seconds"
                    run2.duration_seconds = timeout_seconds
                    await db2.commit()
                    print(f"[run_job_now] Updated run record {run_id} to timeout status")
    except asyncio.CancelledError as e:
        print(f"[run_job_now] Job {job_name} was cancelled: {e}")
        if run_id:
            async with AsyncSessionLocal() as db2:
                result2 = await db2.execute(
                    select(CronRun).where(CronRun.id == run_id)
                )
                run2 = result2.scalar_one_or_none()
                if run2:
                    run2.completed_at = datetime.now(timezone.utc)
                    run2.status = "failed"
                    run2.error_message = str(e) or "Job cancelled by user"
                    if run2.started_at:
                        # Handle timezone-aware/naive datetime comparison
                        started = run2.started_at
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=timezone.utc)
                        run2.duration_seconds = int((run2.completed_at - started).total_seconds())
                    await db2.commit()
                    print(f"[run_job_now] Updated run record {run_id} to cancelled status")
    except Exception as e:
        print(f"[run_job_now] Job {job_name} failed with exception: {e}")
        import traceback
        traceback.print_exc()
        if run_id:
            try:
                async with AsyncSessionLocal() as db2:
                    result2 = await db2.execute(
                        select(CronRun).where(CronRun.id == run_id)
                    )
                    run2 = result2.scalar_one_or_none()
                    if run2:
                        run2.completed_at = datetime.now(timezone.utc)
                        run2.status = "failed"
                        run2.error_message = str(e)
                        if run2.started_at:
                            # Handle timezone-aware/naive datetime comparison
                            started = run2.started_at
                            if started.tzinfo is None:
                                started = started.replace(tzinfo=timezone.utc)
                            run2.duration_seconds = int((run2.completed_at - started).total_seconds())
                        await db2.commit()
                        print(f"[run_job_now] Updated run record {run_id} to failed status")
            except Exception as update_error:
                print(f"[run_job_now] Failed to update run record after exception: {update_error}")
                traceback.print_exc()
    finally:
        if run_id:
            remove_token(run_id)
            print(f"[run_job_now] Cleaned up job {job_name}, run_id: {run_id}")


async def run_cron_job(job_name: str, job_func, *args, **kwargs):
    """Execute a cron job and track its execution with timeout and cancellation."""
    run_id = None
    cancellation_token = None
    try:
        async with AsyncSessionLocal() as db:
            # Get or create cron job record
            result = await db.execute(
                select(CronJob).where(CronJob.name == job_name)
            )
            cron_job = result.scalar_one_or_none()
            
            if not cron_job:
                return
            
            if not cron_job.is_active:
                return
            
            # Create run record
            run = CronRun(
                job_id=cron_job.id,
                job_name=job_name,
                triggered_by="cron",  # Automatically triggered by scheduler
                started_at=datetime.now(timezone.utc),
                status="running"
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id
            
            # Create cancellation token
            cancellation_token = get_cancellation_token(run_id)
            
            # Execute the job with timeout (30 minutes max)
            timeout_seconds = 30 * 60
            try:
                # Job function should create its own DB session, so we don't pass db
                # Instead, we pass run_id and cancellation_token
                result_data = await asyncio.wait_for(
                    job_func(run.id, cancellation_token, *args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                # Job timed out - rollback any pending transactions
                async with AsyncSessionLocal() as db2:
                    await db2.rollback()  # Ensure clean state
                    result2 = await db2.execute(
                        select(CronRun).where(CronRun.id == run_id)
                    )
                    run2 = result2.scalar_one_or_none()
                    if run2:
                        run2.completed_at = datetime.now(timezone.utc)
                        run2.status = "failed"
                        run2.error_message = f"Job timed out after {timeout_seconds} seconds"
                        run2.duration_seconds = timeout_seconds
                        await db2.commit()
                return
            except asyncio.CancelledError as e:
                # Job was cancelled - rollback any pending transactions
                async with AsyncSessionLocal() as db2:
                    await db2.rollback()  # Rollback any pending changes
                    result2 = await db2.execute(
                        select(CronRun).where(CronRun.id == run_id)
                    )
                    run2 = result2.scalar_one_or_none()
                    if run2:
                        run2.completed_at = datetime.now(timezone.utc)
                        run2.status = "failed"
                        run2.error_message = str(e) or "Job cancelled by user"
                        if run2.started_at:
                            run2.duration_seconds = int((run2.completed_at - run2.started_at).total_seconds())
                        await db2.commit()
                return
            
            # Update run record
            async with AsyncSessionLocal() as db2:
                result2 = await db2.execute(
                    select(CronRun).where(CronRun.id == run_id)
                )
                run2 = result2.scalar_one_or_none()
                result3 = await db2.execute(
                    select(CronJob).where(CronJob.id == cron_job.id)
                )
                cron_job2 = result3.scalar_one_or_none()
                
                if run2 and cron_job2:
                    run2.completed_at = datetime.now(timezone.utc)
                    run2.duration_seconds = int((run2.completed_at - run2.started_at).total_seconds())
                    run2.status = result_data.get("status", "success")
                    run2.items_updated = result_data.get("items_updated", 0)
                    
                    # Merge details to preserve logs from update_run_progress
                    existing_details = run2.details or {}
                    new_details = result_data.get("details", {})
                    # Merge: keep existing logs if they exist, otherwise use new logs
                    merged_details = {**existing_details, **new_details}
                    if "logs" in existing_details and "logs" in new_details:
                        # If both have logs, prefer existing (which has all the real-time logs)
                        merged_details["logs"] = existing_details["logs"]
                    elif "logs" in existing_details:
                        # Keep existing logs
                        merged_details["logs"] = existing_details["logs"]
                    elif "logs" in new_details:
                        # Use new logs if no existing logs
                        merged_details["logs"] = new_details["logs"]
                    
                    run2.details = merged_details
                    
                    if run2.status == "failed":
                        run2.error_message = result_data.get("error", "Unknown error")
                        cron_job2.failed_runs += 1
                    else:
                        cron_job2.successful_runs += 1
                    
                    cron_job2.last_run = run2.started_at
                    cron_job2.total_runs += 1
                    cron_job2.updated_at = datetime.now(timezone.utc)
                    await db2.commit()
            
            # Remove cancellation token on successful completion
            if cancellation_token:
                remove_token(run_id)
            
    except Exception as e:
        # Mark as failed if we have a run_id - ensure rollback first
        if run_id:
            async with AsyncSessionLocal() as db:
                await db.rollback()  # Rollback any pending transaction
                result = await db.execute(
                    select(CronRun).where(CronRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.completed_at = datetime.now(timezone.utc)
                    run.status = "failed"
                    run.error_message = str(e)
                    if run.started_at:
                        run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
                    await db.commit()
        
        # Remove cancellation token on error
        if cancellation_token:
            remove_token(run_id)


async def update_finished_games_job():
    """Cron job: Update finished games, standings, and player stats."""
    await run_cron_job("update_finished_games", CronService.update_finished_games)


async def update_player_season_averages_job():
    """Cron job: Batch update player season averages."""
    await run_cron_job(
        "update_player_season_averages",
        CronService.update_player_season_averages_batch,
        batch_size=50
    )


async def update_schedules_job():
    """Cron job: Update team schedules."""
    await run_cron_job("update_schedules", CronService.update_schedules)


async def update_players_team_job():
    """Cron job: Update players' team assignments."""
    await run_cron_job("update_players_team", CronService.update_players_team)


async def update_team_results_job():
    """Cron job: Update team results and standings."""
    await run_cron_job("update_team_results", CronService.update_team_results)


async def initialize_cron_jobs():
    """Initialize cron job definitions in database."""
    async with AsyncSessionLocal() as db:
        jobs = [
            {
                "name": "update_finished_games",
                "description": "Every 2 hours: Update game results, team standings, and player last game stats for games that started in last 12 hours",
                "schedule": "every 2 hours",
                "cron_expression": None,
            },
            {
                "name": "update_player_season_averages",
                "description": "Every 3 days: Batch update player season averages (50 players per run)",
                "schedule": "every 3 days",
                "cron_expression": None,
            },
            {
                "name": "update_schedules",
                "description": "Every 3 days: Check for schedule changes and update games table",
                "schedule": "every 3 days",
                "cron_expression": None,
            },
            {
                "name": "update_players_team",
                "description": "Every 7 days: Update all players' team assignments from NBA API",
                "schedule": "every 7 days",
                "cron_expression": None,
            },
            {
                "name": "update_team_results",
                "description": "Every 24 hours: Comprehensive update of game results and standings",
                "schedule": "every 24 hours",
                "cron_expression": None,
            },
        ]
        
        for job_data in jobs:
            result = await db.execute(
                select(CronJob).where(CronJob.name == job_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                cron_job = CronJob(**job_data)
                db.add(cron_job)
        
        await db.commit()


def start_scheduler():
    """Start the cron scheduler."""
    # Cleanup stuck jobs on startup
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_stuck_jobs())
    
    # Schedule cleanup to run every hour
    scheduler.add_job(
        cleanup_stuck_jobs,
        trigger=IntervalTrigger(hours=1),
        id="cleanup_stuck_jobs",
        name="cleanup_stuck_jobs",
        replace_existing=True
    )
    
    # Schedule jobs
    # Every 2 hours: Update finished games
    scheduler.add_job(
        update_finished_games_job,
        trigger=IntervalTrigger(hours=2),
        id="update_finished_games",
        name="update_finished_games",
        replace_existing=True
    )
    
    # Every 3 days: Update player season averages
    scheduler.add_job(
        update_player_season_averages_job,
        trigger=IntervalTrigger(days=3),
        id="update_player_season_averages",
        name="update_player_season_averages",
        replace_existing=True
    )
    
    # Every 3 days: Update schedules
    scheduler.add_job(
        update_schedules_job,
        trigger=IntervalTrigger(days=3),
        id="update_schedules",
        name="update_schedules",
        replace_existing=True
    )
    
    # Every 7 days: Update players' team assignments
    scheduler.add_job(
        update_players_team_job,
        trigger=IntervalTrigger(days=7),
        id="update_players_team",
        name="update_players_team",
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Cron scheduler started")


def stop_scheduler():
    """Stop the cron scheduler."""
    scheduler.shutdown()
    print("🛑 Cron scheduler stopped")


async def cleanup_stuck_jobs():
    """Mark jobs that have been running for more than 1 hour as failed."""
    async with AsyncSessionLocal() as db:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        result = await db.execute(
            select(CronRun).where(
                CronRun.status == "running",
                CronRun.started_at < one_hour_ago
            )
        )
        stuck_runs = result.scalars().all()
        
        for run in stuck_runs:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = "Job marked as failed - was stuck in running state for over 1 hour"
            if run.started_at:
                # Handle timezone-naive datetime from SQLite
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                completed_at = run.completed_at
                if completed_at.tzinfo is None:
                    completed_at = completed_at.replace(tzinfo=timezone.utc)
                run.duration_seconds = int((completed_at - started_at).total_seconds())
            
            # Cancel token if exists
            cancel_run(run.id, reason="Stuck job cleaned up")
            remove_token(run.id)
            
            # Update job stats
            result2 = await db.execute(
                select(CronJob).where(CronJob.id == run.job_id)
            )
            job = result2.scalar_one_or_none()
            if job:
                job.failed_runs += 1
                job.total_runs += 1
        
        if stuck_runs:
            await db.commit()
            print(f"✅ Cleaned up {len(stuck_runs)} stuck cron jobs")

