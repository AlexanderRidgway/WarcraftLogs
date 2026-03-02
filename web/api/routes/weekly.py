from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Report, Score, Player, AttendanceRecord, GearSnapshot

router = APIRouter(prefix="/api/weekly", tags=["weekly"])


def _week_range(weeks_ago: int = 0):
    """Return (monday_start, sunday_end) for the ISO week `weeks_ago` weeks in the past."""
    today = datetime.utcnow().date()
    # Monday of current week
    monday = today - timedelta(days=today.weekday())
    monday = monday - timedelta(weeks=weeks_ago)
    sunday = monday + timedelta(days=6)
    start = datetime.combine(monday, datetime.min.time())
    end = datetime.combine(sunday, datetime.max.time())
    return start, end


@router.get("")
async def weekly_recap(
    weeks_ago: int = Query(default=0, ge=0, le=52),
    db: AsyncSession = Depends(get_db),
):
    week_start, week_end = _week_range(weeks_ago)
    iso_year, iso_week, _ = week_start.isocalendar()

    # Get reports in this week
    reports_result = await db.execute(
        select(Report)
        .where(Report.start_time >= week_start, Report.start_time <= week_end)
        .order_by(Report.start_time)
    )
    reports = reports_result.scalars().all()
    report_codes = [r.code for r in reports]

    if not report_codes:
        return {
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "report_count": 0,
            "top_performers": [],
            "zone_summaries": [],
            "attendance": [],
            "gear_issues": [],
        }

    # Top Performers: avg overall_score across all reports this week, top 10
    top_result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.count(Score.id).label("fight_count"),
        )
        .join(Player, Score.player_id == Player.id)
        .where(Score.report_code.in_(report_codes))
        .group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
        .limit(10)
    )
    top_performers = [
        {
            "name": row.name,
            "class_name": row.class_name,
            "avg_score": round(row.avg_score, 1),
            "avg_parse": round(row.avg_parse, 1),
            "fight_count": row.fight_count,
        }
        for row in top_result.all()
    ]

    # Zone Summaries: group reports by zone, per zone get top 3 and stats
    zone_groups: dict[str, list] = {}
    for r in reports:
        zone_groups.setdefault(r.zone_name, []).append(r.code)

    zone_summaries = []
    for zone_name, codes in zone_groups.items():
        # Unique players in this zone
        player_count_result = await db.execute(
            select(func.count(func.distinct(Score.player_id)))
            .where(Score.report_code.in_(codes))
        )
        unique_players = player_count_result.scalar() or 0

        # Top 3 by avg score in this zone
        zone_top = await db.execute(
            select(
                Player.name,
                Player.class_name,
                func.avg(Score.overall_score).label("avg_score"),
            )
            .join(Player, Score.player_id == Player.id)
            .where(Score.report_code.in_(codes))
            .group_by(Player.name, Player.class_name)
            .order_by(func.avg(Score.overall_score).desc())
            .limit(3)
        )

        zone_summaries.append({
            "zone_name": zone_name,
            "run_count": len(codes),
            "unique_players": unique_players,
            "top_players": [
                {"name": r.name, "class_name": r.class_name, "avg_score": round(r.avg_score, 1)}
                for r in zone_top.all()
            ],
        })

    # Attendance: players who missed requirements this week
    attendance_result = await db.execute(
        select(AttendanceRecord, Player.name)
        .join(Player, AttendanceRecord.player_id == Player.id)
        .where(
            AttendanceRecord.year == iso_year,
            AttendanceRecord.week_number == iso_week,
            AttendanceRecord.met == False,
        )
        .order_by(Player.name)
    )
    attendance = [
        {
            "player_name": name,
            "zone_label": a.zone_label,
            "clear_count": a.clear_count,
            "required": a.required,
        }
        for a, name in attendance_result.all()
    ]

    # Gear Issues: players with gear problems in this week's reports
    from src.gear.checker import check_player_gear
    from src.config.loader import ConfigLoader

    config = ConfigLoader()
    gear_config = config.get_gear_check()

    # Use only the latest report's gear snapshot per player to avoid duplicates
    latest_report_code = report_codes[-1]  # reports are ordered by start_time asc

    gear_result = await db.execute(
        select(GearSnapshot, Player.name, Player.class_name)
        .join(Player, GearSnapshot.player_id == Player.id)
        .where(GearSnapshot.report_code == latest_report_code)
        .order_by(Player.name, GearSnapshot.slot)
    )

    player_gear: dict[str, dict] = {}
    for g, player_name, class_name in gear_result.all():
        if player_name not in player_gear:
            player_gear[player_name] = {"class_name": class_name, "items": []}
        player_gear[player_name]["items"].append({
            "slot": g.slot,
            "id": g.item_id,
            "itemLevel": g.item_level,
            "quality": g.quality,
            "permanentEnchant": g.permanent_enchant,
            "gems": g.gems or [],
        })

    gear_issues = []
    for player_name, data in player_gear.items():
        result = check_player_gear(data["items"], gear_config)
        if result["issues"] or not result["ilvl_ok"]:
            gear_issues.append({
                "name": player_name,
                "class_name": data["class_name"],
                "avg_ilvl": result["avg_ilvl"],
                "ilvl_ok": result["ilvl_ok"],
                "issue_count": len(result["issues"]),
                "issues": result["issues"],
            })
    gear_issues.sort(key=lambda p: p["issue_count"], reverse=True)
    gear_issues = gear_issues[:15]

    return {
        "week_start": week_start.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "report_count": len(reports),
        "top_performers": top_performers,
        "zone_summaries": zone_summaries,
        "attendance": attendance,
        "gear_issues": gear_issues,
    }
