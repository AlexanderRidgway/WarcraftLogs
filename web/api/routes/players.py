from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Ranking, Score, GearSnapshot, UtilityData, ConsumablesData, AttendanceRecord, Report, User
from web.api.auth import get_current_officer

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("")
async def list_players(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.name))
    players = result.scalars().all()
    return [
        {
            "name": p.name,
            "class_id": p.class_id,
            "class_name": p.class_name,
            "server": p.server,
            "region": p.region,
        }
        for p in players
    ]


@router.get("/{name}")
async def get_player(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    scores_result = await db.execute(
        select(Score).where(Score.player_id == player.id).order_by(Score.recorded_at.desc()).limit(20)
    )
    scores = scores_result.scalars().all()

    return {
        "name": player.name,
        "class_id": player.class_id,
        "class_name": player.class_name,
        "server": player.server,
        "region": player.region,
        "scores": [
            {
                "report_code": s.report_code,
                "spec": s.spec,
                "overall_score": s.overall_score,
                "parse_score": s.parse_score,
                "utility_score": s.utility_score,
                "consumables_score": s.consumables_score,
                "fight_count": s.fight_count,
                "recorded_at": s.recorded_at.isoformat() if s.recorded_at else None,
            }
            for s in scores
        ],
    }


@router.get("/{name}/rankings")
async def get_player_rankings(name: str, weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    rankings_result = await db.execute(
        select(Ranking)
        .where(Ranking.player_id == player.id, Ranking.recorded_at >= cutoff)
        .order_by(Ranking.recorded_at.desc())
    )
    rankings = rankings_result.scalars().all()

    return [
        {
            "encounter_name": r.encounter_name,
            "spec": r.spec,
            "rank_percent": r.rank_percent,
            "zone_id": r.zone_id,
            "report_code": r.report_code,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in rankings
    ]


@router.get("/{name}/gear")
async def get_player_gear(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    latest = await db.execute(
        select(GearSnapshot.report_code)
        .where(GearSnapshot.player_id == player.id)
        .order_by(GearSnapshot.recorded_at.desc())
        .limit(1)
    )
    latest_code = latest.scalar_one_or_none()
    if not latest_code:
        return {"player": name, "gear": [], "issues": []}

    gear_result = await db.execute(
        select(GearSnapshot)
        .where(GearSnapshot.player_id == player.id, GearSnapshot.report_code == latest_code)
    )
    gear = gear_result.scalars().all()

    from src.config.loader import ConfigLoader
    from src.gear.checker import check_player_gear
    config = ConfigLoader()
    gear_config = config.get_gear_check()

    gear_items = [
        {
            "slot": g.slot,
            "id": g.item_id,
            "itemLevel": g.item_level,
            "quality": g.quality,
            "permanentEnchant": g.permanent_enchant,
            "gems": g.gems or [],
        }
        for g in gear
    ]
    check_result = check_player_gear(gear_items, gear_config)

    return {
        "player": name,
        "report_code": latest_code,
        "avg_ilvl": check_result["avg_ilvl"],
        "ilvl_ok": check_result["ilvl_ok"],
        "gear": [
            {
                "slot": g.slot,
                "item_id": g.item_id,
                "item_level": g.item_level,
                "quality": g.quality,
                "permanent_enchant": g.permanent_enchant,
                "gems": g.gems,
            }
            for g in gear
        ],
        "issues": check_result["issues"],
    }


@router.get("/{name}/attendance")
async def get_player_attendance(name: str, weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    records_result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.player_id == player.id)
        .order_by(AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    records = records_result.scalars().all()

    # Get all reports to match zone/week
    reports_result = await db.execute(select(Report).order_by(Report.start_time.desc()))
    all_reports = reports_result.scalars().all()

    # Build a lookup: (year, week, zone_id) -> list of report codes
    report_lookup: dict[tuple, list] = {}
    for rpt in all_reports:
        iso = rpt.start_time.isocalendar()
        key = (iso[0], iso[1], rpt.zone_id)
        if key not in report_lookup:
            report_lookup[key] = []
        report_lookup[key].append({
            "code": rpt.code,
            "date": rpt.start_time.isoformat(),
            "zone_name": rpt.zone_name,
        })

    weeks_data = {}
    for r in records:
        if r.clear_count == 0:
            continue
        key = (r.year, r.week_number)
        if key not in weeks_data:
            weeks_data[key] = {"year": r.year, "week": r.week_number, "zones": []}
        reports = report_lookup.get((r.year, r.week_number, r.zone_id), [])
        weeks_data[key]["zones"].append({
            "zone_id": r.zone_id,
            "zone_label": r.zone_label,
            "clear_count": r.clear_count,
            "required": r.required,
            "met": r.met,
            "reports": reports,
        })

    return list(weeks_data.values())[:weeks]


@router.get("/{name}/trends")
async def get_player_trends(name: str, weeks: int = Query(default=8, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    scores_result = await db.execute(
        select(Score)
        .where(Score.player_id == player.id, Score.recorded_at >= cutoff)
        .order_by(Score.recorded_at.asc())
    )
    scores = scores_result.scalars().all()

    return [
        {
            "date": s.recorded_at.isoformat() if s.recorded_at else None,
            "report_code": s.report_code,
            "overall_score": round(s.overall_score, 1),
            "parse_score": round(s.parse_score, 1),
            "utility_score": round(s.utility_score, 1) if s.utility_score is not None else None,
            "consumables_score": round(s.consumables_score, 1) if s.consumables_score is not None else None,
        }
        for s in scores
    ]


@router.post("/{name}/deactivate")
async def deactivate_player(name: str, officer: User = Depends(get_current_officer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.active = False
    await db.commit()
    return {"status": "ok", "name": name, "active": False}


@router.post("/{name}/activate")
async def activate_player(name: str, officer: User = Depends(get_current_officer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.active = True
    await db.commit()
    return {"status": "ok", "name": name, "active": True}
