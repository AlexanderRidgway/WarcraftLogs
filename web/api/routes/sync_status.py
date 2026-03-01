import asyncio
import logging
import os

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db, async_session
from web.api.auth import get_current_officer
from web.api.models import SyncStatus, User

router = APIRouter(prefix="/api/sync", tags=["sync"])

logger = logging.getLogger(__name__)

# Simple lock to prevent concurrent syncs
_sync_lock = asyncio.Lock()


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


async def _run_sync(force: bool = False):
    """Run a full sync cycle (roster + reports) in the web API process."""
    if _sync_lock.locked():
        logger.info("Sync already in progress, skipping")
        return

    async with _sync_lock:
        from src.api.warcraftlogs import WarcraftLogsClient
        from src.config.loader import ConfigLoader
        from web.api.sync.worker import SyncWorker

        wcl = WarcraftLogsClient(
            client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID", ""),
            client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET", ""),
            api_url=os.getenv("WCL_API_URL", "https://fresh.warcraftlogs.com/api/v2/client"),
        )
        config = ConfigLoader()
        worker = SyncWorker(wcl, config)

        logger.info("Manual sync triggered (force=%s)", force)
        await worker.run_roster_sync()
        await worker.run_reports_sync(force=force)
        logger.info("Manual sync complete")


@router.post("/trigger")
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = False, officer: User = Depends(get_current_officer)):
    if _sync_lock.locked():
        return {"status": "already_running", "message": "Sync is already in progress"}
    background_tasks.add_task(_run_sync, force=force)
    return {"status": "started", "message": "Sync started"}
