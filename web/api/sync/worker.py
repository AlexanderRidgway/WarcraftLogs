import logging
import os
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime (for TIMESTAMP WITHOUT TIME ZONE columns)."""
    return _utcnow().replace(tzinfo=None)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from web.api.database import async_session
from web.api.models import Player, Report, Ranking, Score, GearSnapshot
from web.api.models import UtilityData, ConsumablesData, AttendanceRecord, SyncStatus
from web.api.sync.roster import sync_roster
from web.api.sync.reports import fetch_new_reports, process_report

logger = logging.getLogger(__name__)


class SyncWorker:
    def __init__(self, wcl: WarcraftLogsClient, config: ConfigLoader):
        self.wcl = wcl
        self.config = config
        self.guild_name = os.getenv("GUILD_NAME", "")
        self.server_slug = os.getenv("GUILD_SERVER", "")
        self.region = os.getenv("GUILD_REGION", "US")
        self.scheduler = AsyncIOScheduler()

    def start(self):
        roster_hours = int(os.getenv("ROSTER_SYNC_HOURS", "6"))
        reports_hours = int(os.getenv("SYNC_INTERVAL_HOURS", "2"))

        self.scheduler.add_job(self.run_roster_sync, "interval", hours=roster_hours, id="roster_sync")
        self.scheduler.add_job(self.run_reports_sync, "interval", hours=reports_hours, id="reports_sync")
        self.scheduler.start()
        logger.info("Sync worker started (roster: %dh, reports: %dh)", roster_hours, reports_hours)

    def stop(self):
        self.scheduler.shutdown()

    async def run_roster_sync(self):
        logger.info("Starting roster sync")
        try:
            players = await sync_roster(self.wcl, self.guild_name, self.server_slug, self.region)
            async with async_session() as session:
                for p in players:
                    existing = await session.execute(
                        select(Player).where(Player.name == p["name"])
                    )
                    existing = existing.scalar_one_or_none()
                    if existing:
                        existing.class_id = p["class_id"]
                        existing.class_name = p["class_name"]
                        existing.server = p["server"]
                        existing.region = p["region"]
                        existing.last_synced_at = _utcnow()
                    else:
                        session.add(Player(**p, last_synced_at=_utcnow()))
                await session.commit()

                await self._update_sync_status(session, "roster", "success")
            logger.info("Roster sync complete: %d players", len(players))
        except Exception as e:
            logger.error("Roster sync failed: %s", e)
            async with async_session() as session:
                await self._update_sync_status(session, "roster", "error", str(e))

    async def run_reports_sync(self):
        logger.info("Starting reports sync")
        try:
            async with async_session() as session:
                result = await session.execute(select(Report.code))
                existing_codes = {r[0] for r in result.all()}

            new_reports = await fetch_new_reports(
                self.wcl, self.guild_name, self.server_slug, self.region,
                days_back=7, existing_codes=existing_codes,
            )

            for report_data in new_reports:
                try:
                    await self._process_and_store_report(report_data)
                except Exception as e:
                    logger.warning("Failed to process report %s: %s", report_data["code"], e)

            async with async_session() as session:
                await self._update_sync_status(session, "reports", "success")
            logger.info("Reports sync complete: %d new reports", len(new_reports))
        except Exception as e:
            logger.error("Reports sync failed: %s", e)
            async with async_session() as session:
                await self._update_sync_status(session, "reports", "error", str(e))

    async def _process_and_store_report(self, report_data: dict):
        processed = await process_report(self.wcl, report_data["code"], self.config)

        async with async_session() as session:
            session.add(Report(
                code=report_data["code"],
                zone_id=report_data["zone_id"],
                zone_name=report_data["zone_name"],
                start_time=report_data["start_time"],
                end_time=report_data["end_time"],
                player_names=report_data["player_names"],
            ))

            player_ids = {}
            for name in {r["player_name"] for r in processed["rankings"]}:
                result = await session.execute(select(Player).where(Player.name == name))
                player = result.scalar_one_or_none()
                if player:
                    player_ids[name] = player.id

            for r in processed["rankings"]:
                if r["player_name"] in player_ids:
                    session.add(Ranking(
                        player_id=player_ids[r["player_name"]],
                        encounter_name=r["encounter_name"],
                        spec=r["spec"],
                        rank_percent=r["rank_percent"],
                        zone_id=report_data["zone_id"],
                        report_code=report_data["code"],
                    ))

            for s in processed["scores"]:
                if s["player_name"] in player_ids:
                    session.add(Score(
                        player_id=player_ids[s["player_name"]],
                        report_code=s["report_code"],
                        spec=s["spec"],
                        overall_score=s["overall_score"],
                        parse_score=s["parse_score"],
                        utility_score=s.get("utility_score"),
                        consumables_score=s.get("consumables_score"),
                    ))

            for g in processed["gear"]:
                if g["player_name"] in player_ids:
                    session.add(GearSnapshot(
                        player_id=player_ids[g["player_name"]],
                        report_code=g["report_code"],
                        slot=g["slot"],
                        item_id=g["item_id"],
                        item_level=g["item_level"],
                        quality=g["quality"],
                        permanent_enchant=g.get("permanent_enchant"),
                        gems=g.get("gems"),
                    ))

            for u in processed["utility"]:
                if u["player_name"] in player_ids:
                    session.add(UtilityData(
                        player_id=player_ids[u["player_name"]],
                        report_code=u["report_code"],
                        metric_name=u["metric_name"],
                        label=u["label"],
                        actual_value=u["actual_value"],
                        target_value=u["target_value"],
                        score=u["score"],
                    ))

            for c in processed["consumables"]:
                if c["player_name"] in player_ids:
                    session.add(ConsumablesData(
                        player_id=player_ids[c["player_name"]],
                        report_code=c["report_code"],
                        metric_name=c["metric_name"],
                        label=c["label"],
                        actual_value=c["actual_value"],
                        target_value=c["target_value"],
                        optional=c.get("optional", False),
                    ))

            await session.commit()

    async def _update_sync_status(self, session: AsyncSession, sync_type: str, status: str, error: str = None):
        result = await session.execute(select(SyncStatus).where(SyncStatus.sync_type == sync_type))
        existing = result.scalar_one_or_none()
        now = _utcnow()
        if existing:
            existing.last_run_at = now
            existing.status = status
            existing.error_message = error
        else:
            session.add(SyncStatus(sync_type=sync_type, last_run_at=now, status=status, error_message=error))
        await session.commit()
