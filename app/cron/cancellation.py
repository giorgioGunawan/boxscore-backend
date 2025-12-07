"""Cancellation tokens for cron jobs."""
from typing import Dict, Optional
from datetime import datetime, timezone
import asyncio


class CancellationToken:
    """Token to signal cancellation of a running cron job."""
    
    def __init__(self, run_id: int):
        self.run_id = run_id
        self.cancelled = False
        self.cancelled_at: Optional[datetime] = None
        self.reason: Optional[str] = None
    
    def cancel(self, reason: str = "Cancelled by user"):
        """Mark this token as cancelled."""
        self.cancelled = True
        self.cancelled_at = datetime.now(timezone.utc)
        self.reason = reason
    
    def check(self):
        """Raise CancelledError if cancelled."""
        if self.cancelled:
            raise asyncio.CancelledError(f"Job cancelled: {self.reason}")


# Global registry of active cancellation tokens
_active_tokens: Dict[int, CancellationToken] = {}


def get_cancellation_token(run_id: int) -> CancellationToken:
    """Get or create a cancellation token for a run."""
    if run_id not in _active_tokens:
        _active_tokens[run_id] = CancellationToken(run_id)
    return _active_tokens[run_id]


def cancel_run(run_id: int, reason: str = "Cancelled by user") -> bool:
    """Cancel a running cron job."""
    if run_id in _active_tokens:
        _active_tokens[run_id].cancel(reason)
        return True
    return False


def remove_token(run_id: int):
    """Remove a cancellation token (called when job completes)."""
    _active_tokens.pop(run_id, None)

