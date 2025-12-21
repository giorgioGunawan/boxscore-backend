"""Admin API for cron job management."""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CronJob, CronRun
from app.cron.scheduler import scheduler, cleanup_stuck_jobs
from app.cron.cancellation import cancel_run, get_cancellation_token

router = APIRouter(prefix="/admin/cron", tags=["admin-cron"])


def safe_isoformat(dt):
    """Safely convert datetime to ISO format, handling timezone-naive datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


@router.get("/jobs")
async def list_cron_jobs(db: AsyncSession = Depends(get_db)):
    """List all cron jobs with their status."""
    result = await db.execute(
        select(CronJob).order_by(CronJob.name)
    )
    jobs = result.scalars().all()
    
    # Get scheduler job info
    scheduler_jobs = {job.id: job for job in scheduler.get_jobs()}
    
    jobs_data = []
    for job in jobs:
        scheduler_job = scheduler_jobs.get(job.name) if scheduler_jobs else None
        
        # Calculate success rate
        success_rate = 0.0
        if job.total_runs > 0:
            success_rate = (job.successful_runs / job.total_runs) * 100
        
        # Get next run time from scheduler
        next_run = None
        if scheduler_job and hasattr(scheduler_job, 'next_run_time') and scheduler_job.next_run_time:
            next_run = scheduler_job.next_run_time.isoformat()
        
        jobs_data.append({
            "id": job.id,
            "name": job.name,
            "description": job.description,
            "schedule": job.schedule,
            "is_active": job.is_active,
            "last_run": safe_isoformat(job.last_run),
            "next_run": next_run,
            "total_runs": job.total_runs,
            "successful_runs": job.successful_runs,
            "failed_runs": job.failed_runs,
            "success_rate": round(success_rate, 1),
            "scheduler_status": "scheduled" if scheduler_job else "not_scheduled",
        })
    
    return {"jobs": jobs_data, "count": len(jobs_data)}


@router.get("/jobs/{job_id}/runs")
async def list_cron_runs(
    job_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db)
):
    """List cron runs for a specific job."""
    result = await db.execute(
        select(CronRun)
        .where(CronRun.job_id == job_id)
        .order_by(desc(CronRun.started_at))
        .offset(offset)
        .limit(limit)
    )
    runs = result.scalars().all()
    
    # Get total count
    count_result = await db.execute(
        select(func.count(CronRun.id)).where(CronRun.job_id == job_id)
    )
    total = count_result.scalar_one()
    
    runs_data = []
    for run in runs:
        runs_data.append({
            "id": run.id,
            "job_id": run.job_id,
            "job_name": run.job_name,
            "triggered_by": getattr(run, 'triggered_by', 'cron'),
            "started_at": safe_isoformat(run.started_at),
            "completed_at": safe_isoformat(run.completed_at),
            "status": run.status,
            "duration_seconds": run.duration_seconds,
            "items_updated": run.items_updated,
            "error_message": run.error_message,
            "details": run.details,
        })
    
    return {
        "runs": runs_data,
        "count": len(runs_data),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/runs")
async def list_all_runs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    status: Optional[str] = Query(default=None),
    job_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """List all cron runs across all jobs."""
    query = select(CronRun).order_by(desc(CronRun.started_at))
    
    if status:
        query = query.where(CronRun.status == status)
    if job_name:
        query = query.where(CronRun.job_name == job_name)
    
    # Get total count
    count_query = select(func.count(CronRun.id))
    if status:
        count_query = count_query.where(CronRun.status == status)
    if job_name:
        count_query = count_query.where(CronRun.job_name == job_name)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    result = await db.execute(query.offset(offset).limit(limit))
    runs = result.scalars().all()
    
    runs_data = []
    for run in runs:
        runs_data.append({
            "id": run.id,
            "job_id": run.job_id,
            "job_name": run.job_name,
            "triggered_by": getattr(run, 'triggered_by', 'cron'),
            "started_at": safe_isoformat(run.started_at),
            "completed_at": safe_isoformat(run.completed_at),
            "status": run.status,
            "duration_seconds": run.duration_seconds,
            "items_updated": run.items_updated,
            "error_message": run.error_message,
            "details": run.details,
        })
    
    return {
        "runs": runs_data,
        "count": len(runs_data),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/jobs/{job_id}/trigger")
async def trigger_cron_job(
    job_id: int,
    hours_back: int = Query(default=7),
    team_id: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None),
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a cron job with optional parameters."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    
    # Trigger the job directly - run in background (no cron table checks)
    import asyncio
    from app.cron.scheduler import run_job_now
    from app.services.cron_service import CronService
    
    job_functions = {
        "update_finished_games": lambda run_id, cancellation_token=None: CronService.update_finished_games(run_id, cancellation_token, hours_back=hours_back, force=force),
        "update_player_season_averages": lambda run_id, cancellation_token=None: CronService.update_player_season_averages_batch(run_id, cancellation_token, batch_size=50, force=force),
        "update_schedules": lambda run_id, cancellation_token=None: CronService.update_schedules(run_id, cancellation_token, force=force),
        "update_players_team": lambda run_id, cancellation_token=None: CronService.update_players_team(run_id, cancellation_token, batch_size=50),
        "update_team_results": lambda run_id, cancellation_token=None: CronService.update_team_results(run_id, cancellation_token, team_id=team_id, limit=limit, force=force),
    }
    
    if job.name not in job_functions:
        raise HTTPException(status_code=400, detail=f"Unknown job: {job.name}")
    
    print(f"[trigger_cron_job] Triggering job: {job.name} with team_id={team_id}, limit={limit}, force={force}")
    
    # Create and store the task to prevent garbage collection
    task = asyncio.create_task(run_job_now(job.name, job_functions[job.name]))
    
    # Add task to a set to keep it alive (prevent GC)
    if not hasattr(trigger_cron_job, '_background_tasks'):
        trigger_cron_job._background_tasks = set()
    
    trigger_cron_job._background_tasks.add(task)
    
    # Add callback to log completion and remove from set
    def task_done_callback(task):
        try:
            # Check if task raised an exception
            exc = task.exception()
            if exc:
                print(f"[trigger_cron_job] Task {job.name} failed with exception: {exc}")
                import traceback
                traceback.print_exception(type(exc), exc, exc.__traceback__)
            else:
                print(f"[trigger_cron_job] Task {job.name} completed successfully")
        except asyncio.CancelledError:
            print(f"[trigger_cron_job] Task {job.name} was cancelled")
        except Exception as e:
            print(f"[trigger_cron_job] Error in task callback: {e}")
        finally:
            # Remove from set
            trigger_cron_job._background_tasks.discard(task)
    
    task.add_done_callback(task_done_callback)
    
    print(f"[trigger_cron_job] Task created for job: {job.name}")
    
    return {"message": f"Job {job.name} triggered successfully - running in background"}


@router.put("/jobs/{job_id}/toggle")
async def toggle_cron_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Enable or disable a cron job."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    
    job.is_active = not job.is_active
    job.updated_at = datetime.now(timezone.utc)
    
    # Also update scheduler
    if job.is_active:
        # Re-add job to scheduler (would need to implement based on job name)
        pass
    else:
        # Remove job from scheduler
        try:
            scheduler.remove_job(job.name)
        except:
            pass
    
    await db.commit()
    
    return {
        "id": job.id,
        "name": job.name,
        "is_active": job.is_active,
        "message": f"Job {'enabled' if job.is_active else 'disabled'}"
    }


@router.get("/runs/{run_id}/logs")
async def get_cron_run_logs(
    run_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get logs/details for a specific cron run."""
    try:
        result = await db.execute(select(CronRun).where(CronRun.id == run_id))
        run = result.scalar_one_or_none()
        
        if not run:
            raise HTTPException(status_code=404, detail="Cron run not found")
        
        # Calculate elapsed time if still running
        elapsed_seconds = None
        is_stuck = False
        if run.status == "running" and run.started_at:
            try:
                # Ensure both datetimes are timezone-aware
                now = datetime.now(timezone.utc)
                started = run.started_at
                
                # If started_at is naive, assume it's UTC
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                
                elapsed = now - started
                elapsed_seconds = int(elapsed.total_seconds())
                # Check if stuck (running for more than 1 hour)
                is_stuck = elapsed_seconds > 3600
            except Exception as e:
                print(f"Error calculating elapsed time for run {run_id}: {e}")
                elapsed_seconds = None
                is_stuck = False
    
        return {
            "id": run.id,
            "job_name": run.job_name,
            "triggered_by": getattr(run, 'triggered_by', 'cron'),
            "status": "stuck" if is_stuck else run.status,
            "started_at": safe_isoformat(run.started_at),
            "completed_at": safe_isoformat(run.completed_at),
            "duration_seconds": run.duration_seconds,
            "elapsed_seconds": elapsed_seconds,
            "items_updated": run.items_updated,
            "error_message": run.error_message or ("Job appears to be stuck (running for over 1 hour)" if is_stuck else None),
            "details": run.details,
            "is_running": run.status == "running" and not is_stuck,
            "is_stuck": is_stuck,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cron run logs: {str(e)}")


@router.post("/cleanup-stuck")
async def cleanup_stuck_jobs_endpoint():
    """Manually trigger cleanup of stuck cron jobs."""
    await cleanup_stuck_jobs()
    return {"message": "Cleanup completed"}


@router.post("/runs/{run_id}/stop")
async def stop_cron_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Stop a running cron job."""
    try:
        # Check if run exists
        result = await db.execute(select(CronRun).where(CronRun.id == run_id))
        run = result.scalar_one_or_none()
        
        if not run:
            raise HTTPException(status_code=404, detail="Cron run not found")
        
        # Check if stuck (running for more than 1 hour)
        is_stuck = False
        try:
            if run.status == "running" and run.started_at:
                now = datetime.now(timezone.utc)
                started = run.started_at
                
                # If started_at is naive, assume it's UTC
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                
                elapsed = now - started
                elapsed_seconds = int(elapsed.total_seconds())
                is_stuck = elapsed_seconds > 3600
        except Exception as e:
            # If we can't calculate elapsed time, assume it's not stuck
            print(f"Error calculating elapsed time for run {run_id}: {e}")
            is_stuck = False
        
        # If already completed and not stuck, return success
        if run.status != "running" and not is_stuck:
            return {
                "message": f"Cron run {run_id} is already {run.status}",
                "run_id": run_id,
                "job_name": run.job_name,
                "status": run.status
            }
        
        # Try to cancel via token first (don't fail if this doesn't work)
        try:
            cancel_run(run_id, reason="Stopped by user")
        except Exception as e:
            print(f"Error cancelling token for run {run_id}: {e}")
            # Continue anyway - we'll update the DB directly
        
        # Also directly mark as failed in database (in case token doesn't work)
        try:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = "Stopped by user"
            if run.started_at:
                try:
                    started = run.started_at
                    # If started_at is naive, assume it's UTC
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    run.duration_seconds = int((run.completed_at - started).total_seconds())
                except Exception as e:
                    print(f"Error calculating duration for run {run_id}: {e}")
                    run.duration_seconds = None
            
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update run status: {str(e)}")
        
        return {
            "message": f"Cron run {run_id} stopped successfully",
            "run_id": run_id,
            "job_name": run.job_name,
            "status": "failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping cron run: {str(e)}")


@router.delete("/runs/{run_id}")
async def delete_cron_run(
    run_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a cron run record."""
    try:
        result = await db.execute(select(CronRun).where(CronRun.id == run_id))
        run = result.scalar_one_or_none()
        
        if not run:
            raise HTTPException(status_code=404, detail="Cron run not found")
        
        # If running, stop it first
        if run.status == "running":
            try:
                cancel_run(run_id, reason="Deleted by user")
            except Exception as e:
                print(f"Error cancelling token for run {run_id}: {e}")
            
            try:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = "Deleted by user"
                if run.started_at:
                    try:
                        started = run.started_at
                        # If started_at is naive, assume it's UTC
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=timezone.utc)
                        run.duration_seconds = int((run.completed_at - started).total_seconds())
                    except Exception as e:
                        print(f"Error calculating duration for run {run_id}: {e}")
                        run.duration_seconds = None
                await db.commit()
            except Exception as e:
                await db.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to stop running job: {str(e)}")
        
        # Delete the run
        try:
            await db.execute(delete(CronRun).where(CronRun.id == run_id))
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete run: {str(e)}")
        
        # Remove token if exists
        try:
            from app.cron.cancellation import remove_token
            remove_token(run_id)
        except Exception as e:
            print(f"Error removing token for run {run_id}: {e}")
        
        return {
            "message": f"Cron run {run_id} deleted successfully",
            "run_id": run_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting cron run: {str(e)}")

