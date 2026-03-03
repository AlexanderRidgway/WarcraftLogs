from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.loader import ConfigLoader
from web.api.database import get_db
from web.api.models import Report, Score, ConsumablesData, Player, Fight, Death, Ranking, UtilityData, GearSnapshot

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    excluded = ConfigLoader().get_excluded_zones()
    result = await db.execute(select(Report).order_by(Report.start_time.desc()))
    reports = result.scalars().all()

    out = []
    for r in reports:
        # Aggregate fight stats
        fight_result = await db.execute(
            select(
                func.sum(case((Fight.kill == True, 1), else_=0)).label("kill_count"),
                func.sum(case((Fight.kill == False, 1), else_=0)).label("wipe_count"),
            ).where(Fight.report_code == r.code)
        )
        fight_row = fight_result.first()

        # Count deaths
        death_result = await db.execute(
            select(func.count(Death.id))
            .join(Fight, Death.fight_db_id == Fight.id)
            .where(Fight.report_code == r.code)
        )
        death_count = death_result.scalar() or 0

        # Average parse from rankings (exclude "Average" entries for per-boss granularity)
        parse_result = await db.execute(
            select(func.avg(Score.parse_score))
            .where(Score.report_code == r.code)
        )
        avg_parse = parse_result.scalar()

        out.append({
            "code": r.code,
            "zone_id": r.zone_id,
            "zone_name": r.zone_name,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat(),
            "player_count": len(r.player_names) if r.player_names else 0,
            "kill_count": int(fight_row.kill_count or 0) if fight_row else 0,
            "wipe_count": int(fight_row.wipe_count or 0) if fight_row else 0,
            "death_count": death_count,
            "avg_parse": round(avg_parse, 1) if avg_parse else None,
            "informational": r.zone_id in excluded if excluded else False,
        })

    return out


@router.get("/{code}")
async def get_report(code: str, db: AsyncSession = Depends(get_db)):
    excluded = ConfigLoader().get_excluded_zones()
    result = await db.execute(select(Report).where(Report.code == code))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    scores_result = await db.execute(
        select(Score, Player.name, Player.class_name)
        .join(Player, Score.player_id == Player.id)
        .where(Score.report_code == code)
        .order_by(Score.overall_score.desc())
    )
    scores = scores_result.all()

    consumables_result = await db.execute(
        select(ConsumablesData, Player.name)
        .join(Player, ConsumablesData.player_id == Player.id)
        .where(ConsumablesData.report_code == code)
    )
    consumables = consumables_result.all()

    # Build consumable flags (flask/elixir + potion pass/fail per player)
    player_consumables: dict[str, dict[str, float]] = {}
    for c, name in consumables:
        player_consumables.setdefault(name, {})[c.metric_name] = c.actual_value

    consumable_flags = []
    for player_name, metrics in player_consumables.items():
        # flask_or_elixir is a combo_presence metric: 0 = none, 100 = has flask or both elixirs
        flask_or_elixir = metrics.get("flask_or_elixir", 0)
        flask_ok = flask_or_elixir > 50

        haste = metrics.get("haste_potion_count", 0)
        destro = metrics.get("destruction_potion_count", 0)
        mana = metrics.get("mana_potion_count", 0)
        potion_ok = (haste + destro + mana) >= 1

        reasons = []
        if not flask_ok:
            reasons.append("No flask/elixirs")
        if not potion_ok:
            reasons.append("No potions")

        consumable_flags.append({
            "player_name": player_name,
            "flask_ok": flask_ok,
            "potion_ok": potion_ok,
            "passed": flask_ok and potion_ok,
            "reasons": reasons,
        })

    # Per-boss rankings
    rankings_result = await db.execute(
        select(Ranking, Player.name)
        .join(Player, Ranking.player_id == Player.id)
        .where(Ranking.report_code == code, Ranking.encounter_name != "Average")
        .order_by(Ranking.encounter_name, Ranking.rank_percent.desc())
    )
    rankings_rows = rankings_result.all()

    boss_rankings: dict[str, list] = {}
    for r, player_name in rankings_rows:
        boss_rankings.setdefault(r.encounter_name, []).append({
            "player_name": player_name,
            "spec": r.spec,
            "rank_percent": r.rank_percent,
        })

    return {
        "code": report.code,
        "zone_id": report.zone_id,
        "zone_name": report.zone_name,
        "start_time": report.start_time.isoformat(),
        "end_time": report.end_time.isoformat(),
        "player_names": report.player_names,
        "informational": report.zone_id in excluded if excluded else False,
        "scores": [
            {
                "player_name": name,
                "class_name": class_name,
                "spec": s.spec,
                "overall_score": s.overall_score,
                "parse_score": s.parse_score,
                "utility_score": s.utility_score,
                "consumables_score": s.consumables_score,
            }
            for s, name, class_name in scores
        ],
        "consumables": [
            {
                "player_name": name,
                "metric_name": c.metric_name,
                "label": c.label,
                "actual_value": c.actual_value,
                "target_value": c.target_value,
                "optional": c.optional,
            }
            for c, name in consumables
        ],
        "boss_rankings": boss_rankings,
        "consumable_flags": consumable_flags,
    }


@router.get("/{code}/utility")
async def get_report_utility(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.code == code))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Report not found")

    rows = await db.execute(
        select(UtilityData, Player.name, Player.class_name)
        .join(Player, UtilityData.player_id == Player.id)
        .where(UtilityData.report_code == code)
        .order_by(Player.name, UtilityData.metric_name)
    )

    players: dict[str, dict] = {}
    for u, player_name, class_name in rows.all():
        if player_name not in players:
            players[player_name] = {
                "player_name": player_name,
                "class_name": class_name,
                "metrics": [],
            }
        players[player_name]["metrics"].append({
            "metric_name": u.metric_name,
            "label": u.label,
            "actual_value": u.actual_value,
            "target_value": u.target_value,
            "score": u.score,
        })

    return list(players.values())


@router.get("/{code}/gear")
async def get_report_gear(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.code == code))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Report not found")

    rows = await db.execute(
        select(GearSnapshot, Player.name, Player.class_name)
        .join(Player, GearSnapshot.player_id == Player.id)
        .where(GearSnapshot.report_code == code)
        .order_by(Player.name, GearSnapshot.slot)
    )

    from src.gear.checker import check_player_gear
    from src.config.loader import ConfigLoader

    config = ConfigLoader()
    gear_config = config.get_gear_check()

    # Group gear items by player
    player_gear: dict[str, dict] = {}
    for g, player_name, class_name in rows.all():
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

    players = []
    for player_name, data in player_gear.items():
        result = check_player_gear(data["items"], gear_config)
        players.append({
            "name": player_name,
            "class_name": data["class_name"],
            "avg_ilvl": result["avg_ilvl"],
            "ilvl_ok": result["ilvl_ok"],
            "issues": result["issues"],
            "issue_count": len(result["issues"]),
        })

    players.sort(key=lambda p: p["issue_count"], reverse=True)
    flagged = sum(1 for p in players if p["issue_count"] > 0 or not p["ilvl_ok"])

    return {
        "total_players": len(players),
        "passed": len(players) - flagged,
        "flagged": flagged,
        "gear_config": gear_config,
        "players": players,
    }
