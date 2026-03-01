import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from web.api.database import engine
from web.api.models import Base
from web.api.sync.worker import SyncWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    wcl = WarcraftLogsClient(
        client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID", ""),
        client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET", ""),
        api_url=os.getenv("WCL_API_URL", "https://fresh.warcraftlogs.com/api/v2/client"),
    )
    config = ConfigLoader()

    worker = SyncWorker(wcl, config)

    logger.info("Running initial sync...")
    await worker.run_roster_sync()
    await worker.run_reports_sync()

    worker.start()
    logger.info("Sync worker running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
