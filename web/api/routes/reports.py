from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Report, Score, ConsumablesData, Player, Fight, Death, Ranking

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
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
        })

    return out


@router.get("/{code}")
async def get_report(code: str, db: AsyncSession = Depends(get_db)):
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
    }
