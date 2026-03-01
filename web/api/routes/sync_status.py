from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import SyncStatus

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SyncStatus))
    statuses = result.scalars().all()
    return [
        {
            "sync_type": s.sync_type,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
            "status": s.status,
            "error_message": s.error_message,
        }
        for s in statuses
    ]
