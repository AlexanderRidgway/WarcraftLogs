import logging
import os
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime (for TIMESTAMP WITHOUT TIME ZONE columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from web.api.database import async_session
from web.api.models import Player, Report, Ranking, Score, GearSnapshot
from web.api.models import UtilityData, ConsumablesData, AttendanceRecord, SyncStatus
from web.api.models import Fight, Death, FightPlayerStats, Badge
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

    async def run_reports_sync(self, force: bool = False):
        logger.info("Starting reports sync (force=%s)", force)
        try:
            if force:
                # Clear all report-related data to re-process from scratch
                async with async_session() as session:
                    await session.execute(delete(Badge))
                    await session.execute(delete(Death))
                    await session.execute(delete(FightPlayerStats))
                    await session.execute(delete(Fight))
                    await session.execute(delete(Ranking))
                    await session.execute(delete(Score))
                    await session.execute(delete(GearSnapshot))
                    await session.execute(delete(UtilityData))
                    await session.execute(delete(ConsumablesData))
                    await session.execute(delete(Report))
                    await session.commit()
                    logger.info("Cleared all report data for full resync")
                existing_codes = set()
            else:
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

            # Always recompute attendance from all synced reports
            await self._compute_attendance()

            # Evaluate badges
            try:
                async with async_session() as session:
                    from web.api.badges import evaluate_badges
                    await evaluate_badges(session)
            except Exception as e:
                logger.warning("Badge evaluation failed: %s", e)

            async with async_session() as session:
                await self._update_sync_status(session, "reports", "success")
            logger.info("Reports sync complete: %d new reports", len(new_reports))
        except Exception as e:
            logger.error("Reports sync failed: %s", e)
            async with async_session() as session:
                await self._update_sync_status(session, "reports", "error", str(e))

    async def _process_and_store_report(self, report_data: dict):
        # Build player class map from roster for accurate spec keys
        player_classes = {}
        async with async_session() as session:
            players_result = await session.execute(select(Player))
            for p in players_result.scalars().all():
                player_classes[p.name] = p.class_name

        processed = await process_report(self.wcl, report_data["code"], self.config, player_classes)

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

            # Store fights
            fight_db_ids = {}
            for f in processed.get("fights", []):
                fight = Fight(**f)
                session.add(fight)
                await session.flush()
                fight_db_ids[f["fight_id"]] = fight.id

            # Store deaths
            for d in processed.get("deaths", []):
                db_fight_id = fight_db_ids.get(d["fight_id"])
                player_id = player_ids.get(d["player_name"])
                if db_fight_id and player_id:
                    session.add(Death(
                        fight_db_id=db_fight_id,
                        player_id=player_id,
                        timestamp_ms=d["timestamp_ms"],
                        killing_ability=d.get("killing_ability"),
                        damage_taken=d.get("damage_taken"),
                    ))

            # Store fight player stats
            for s in processed.get("fight_stats", []):
                db_fight_id = fight_db_ids.get(s["fight_id"])
                player_id = player_ids.get(s["player_name"])
                if db_fight_id and player_id:
                    session.add(FightPlayerStats(
                        fight_db_id=db_fight_id,
                        player_id=player_id,
                        dps=s["dps"],
                        hps=s["hps"],
                        damage_done=s["damage_done"],
                        healing_done=s["healing_done"],
                        deaths_count=s["deaths_count"],
                    ))

            await session.commit()

    async def _compute_attendance(self):
        """Compute attendance records from all synced reports and attendance requirements."""
        requirements = self.config.get_attendance()
        if not requirements:
            logger.info("No attendance requirements configured, skipping attendance computation")
            return

        async with async_session() as session:
            # Load all reports and players
            reports_result = await session.execute(select(Report).order_by(Report.start_time))
            reports = reports_result.scalars().all()

            players_result = await session.execute(select(Player))
            players = players_result.scalars().all()
            player_map = {p.name: p.id for p in players}

            # Group reports by ISO week
            weeks: dict[tuple[int, int], list[Report]] = {}
            for report in reports:
                iso = report.start_time.isocalendar()
                key = (iso[0], iso[1])
                weeks.setdefault(key, []).append(report)

            # Clear existing attendance records and recompute
            await session.execute(delete(AttendanceRecord))

            for (year, week_num), week_reports in weeks.items():
                for req in requirements:
                    zone_id = req["zone_id"]
                    required = req["required_per_week"]

                    # Count per-player appearances in this zone this week
                    player_counts: dict[str, int] = {}
                    for report in week_reports:
                        if report.zone_id != zone_id:
                            continue
                        for name in (report.player_names or []):
                            player_counts[name] = player_counts.get(name, 0) + 1

                    # Create attendance records for all known players
                    for player_name, player_id in player_map.items():
                        count = player_counts.get(player_name, 0)
                        session.add(AttendanceRecord(
                            player_id=player_id,
                            year=year,
                            week_number=week_num,
                            zone_id=zone_id,
                            zone_label=req["label"],
                            clear_count=count,
                            required=required,
                            met=count >= required,
                        ))

            await session.commit()
            logger.info("Attendance computation complete: %d weeks, %d players", len(weeks), len(player_map))

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
