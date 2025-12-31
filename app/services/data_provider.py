"""
Hybrid Data Provider - Local DB first, NBA API as fallback/sync

Priority Logic:
1. If manual override exists -> Return local data
2. If fresh data exists (within TTL) -> Return local data
3. Try to sync from NBA API -> Store and return
4. If API fails -> Return stale local data with flag
"""

from datetime import datetime, timedelta
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings

settings = get_settings()


class DataProvider:
    """Hybrid data provider with local-first, API-fallback strategy."""
    
    # TTL settings (in seconds)
    TTL_PLAYER_STATS = 3600  # 1 hour
    TTL_TEAM_STANDINGS = 1800  # 30 minutes
    TTL_GAMES = 3600  # 1 hour
    TTL_PLAYER_INFO = 86400  # 24 hours
    
    @staticmethod
    def is_fresh(last_sync: Optional[datetime], ttl_seconds: int) -> bool:
        """Check if data is still fresh based on last sync time."""
        if not last_sync:
            return False
        return datetime.utcnow() - last_sync < timedelta(seconds=ttl_seconds)
    
    @staticmethod
    def is_manual_override(record: Any) -> bool:
        """Check if a record has manual override enabled."""
        return getattr(record, 'is_manual_override', False)
    
    @staticmethod
    def add_metadata(data: dict, record: Any, is_stale: bool = False) -> dict:
        """Add source metadata to response."""
        data['_meta'] = {
            'source': getattr(record, 'source', 'api'),
            'is_manual_override': getattr(record, 'is_manual_override', False),
            'last_api_sync': getattr(record, 'last_api_sync', None),
            'last_manual_edit': getattr(record, 'last_manual_edit', None),
            'is_stale': is_stale,
        }
        # Convert datetime to ISO string for JSON serialization
        if data['_meta']['last_api_sync']:
            data['_meta']['last_api_sync'] = data['_meta']['last_api_sync'].isoformat()
        if data['_meta']['last_manual_edit']:
            data['_meta']['last_manual_edit'] = data['_meta']['last_manual_edit'].isoformat()
        return data


class HybridDataService:
    """
    Base class for hybrid data services.
    Provides common patterns for API-first with local override.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_with_fallback(
        self,
        local_fetch_fn,
        api_fetch_fn,
        store_fn,
        ttl_seconds: int,
        force_refresh: bool = False,
    ) -> tuple[Any, bool]:
        """
        Generic pattern for hybrid data fetching.
        
        Returns: (data, is_stale)
        """
        # 1. Try to get local data
        local_data = await local_fetch_fn()
        
        if local_data:
            # 2. If manual override, always use local
            if DataProvider.is_manual_override(local_data):
                return local_data, False
            
            # 3. If fresh and not forcing refresh, use local
            if not force_refresh and DataProvider.is_fresh(
                getattr(local_data, 'last_api_sync', None), 
                ttl_seconds
            ):
                return local_data, False
        
        # 4. Try to fetch from API
        try:
            api_data = await api_fetch_fn()
            
            if api_data:
                # Store the new data
                stored_data = await store_fn(api_data)
                return stored_data, False
        except Exception as e:
            print(f"API fetch failed: {e}")
        
        # 5. Fallback to local data (even if stale)
        if local_data:
            return local_data, True
        
        return None, False


# Helper functions for manual data entry
async def set_manual_override(
    db: AsyncSession,
    model_class,
    record_id: int,
    override_data: dict,
    reason: str = None,
) -> Any:
    """
    Set manual override on a record.
    Updates the record with provided data and marks it as manually overridden.
    """
    result = await db.execute(
        select(model_class).where(model_class.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        return None
    
    # Update fields from override_data
    for key, value in override_data.items():
        if hasattr(record, key) and key not in ['id', 'created_at']:
            setattr(record, key, value)
    
    # Set override metadata
    record.source = 'manual'
    record.is_manual_override = True
    record.override_reason = reason
    record.last_manual_edit = datetime.utcnow()
    
    await db.commit()
    await db.refresh(record)
    
    return record


async def clear_manual_override(
    db: AsyncSession,
    model_class,
    record_id: int,
) -> Any:
    """
    Clear manual override on a record.
    The next API sync will update the data.
    """
    result = await db.execute(
        select(model_class).where(model_class.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        return None
    
    record.is_manual_override = False
    record.override_reason = None
    
    await db.commit()
    await db.refresh(record)
    
    return record


async def create_manual_record(
    db: AsyncSession,
    model_class,
    data: dict,
    reason: str = None,
) -> Any:
    """
    Create a new record with manual data (not from API).
    """
    record = model_class(**data)
    record.source = 'manual'
    record.is_manual_override = True
    record.override_reason = reason
    record.last_manual_edit = datetime.utcnow()
    record.created_at = datetime.utcnow()
    
    db.add(record)
    await db.commit()
    await db.refresh(record)
    
    return record

