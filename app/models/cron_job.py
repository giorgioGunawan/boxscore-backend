"""Cron job tracking models."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timezone


class CronJob(Base):
    """Tracks cron job definitions and schedules."""
    __tablename__ = "cron_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    schedule = Column(String(100), nullable=False)  # e.g., "every 2 hours", "every 3 days"
    cron_expression = Column(String(100), nullable=True)  # For APScheduler
    is_active = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    runs = relationship("CronRun", back_populates="job")
    
    def __repr__(self):
        return f"<CronJob {self.name}>"


class CronRun(Base):
    """Tracks individual cron job executions."""
    __tablename__ = "cron_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("cron_jobs.id"), nullable=False)
    job_name = Column(String(100), nullable=False)
    triggered_by = Column(String(20), default='cron', nullable=False)  # 'cron' or 'manual'
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # 'running', 'success', 'failed'
    duration_seconds = Column(Integer, nullable=True)
    items_updated = Column(Integer, default=0)  # How many records were updated
    error_message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Store additional info like which teams/players were updated
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship (back reference)
    job = relationship("CronJob", back_populates="runs")
    
    def __repr__(self):
        return f"<CronRun {self.job_name} - {self.status}>"

