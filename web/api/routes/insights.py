from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from src.config.loader import ConfigLoader
from web.api.database import get_db
from web.api.models import Player, Score, Ranking, UtilityData, ConsumablesData, Report

router = APIRouter(prefix="/api/players", tags=["insights"])


@router.get("/{name}/insights")
async def get_player_insights(name: str, weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    excluded = ConfigLoader().get_excluded_zones()
    insights = []

    # 1. Score trend analysis
    score_query = (
        select(Score)
        .join(Report, Report.code == Score.report_code)
        .where(Score.player_id == player.id, Score.recorded_at >= cutoff)
    )
    if excluded:
        score_query = score_query.where(Report.zone_id.notin_(excluded))
    scores_result = await db.execute(score_query.order_by(Score.recorded_at.asc()))
    scores = scores_result.scalars().all()

    if len(scores) >= 2:
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        avg_first = sum(s.overall_score for s in first_half) / len(first_half)
        avg_second = sum(s.overall_score for s in second_half) / len(second_half)
        diff = round(avg_second - avg_first, 1)
        if diff >= 5:
            insights.append({
                "type": "success",
                "message": f"Overall score improved by {diff} points over the last {weeks} weeks",
                "metric": "overall_score",
            })
        elif diff <= -5:
            insights.append({
                "type": "warning",
                "message": f"Overall score declined by {abs(diff)} points over the last {weeks} weeks",
                "metric": "overall_score",
            })

    # 2. Utility metric gaps
    util_query = (
        select(
            UtilityData.label,
            func.avg(UtilityData.actual_value).label("avg_actual"),
            func.avg(UtilityData.target_value).label("avg_target"),
        )
        .join(Score, (Score.player_id == UtilityData.player_id) & (Score.report_code == UtilityData.report_code))
        .join(Report, Report.code == UtilityData.report_code)
        .where(UtilityData.player_id == player.id, Score.recorded_at >= cutoff)
    )
    if excluded:
        util_query = util_query.where(Report.zone_id.notin_(excluded))
    utility_result = await db.execute(util_query.group_by(UtilityData.label))
    for row in utility_result.all():
        if row.avg_target > 0:
            pct = (row.avg_actual / row.avg_target) * 100
            if pct < 85:
                insights.append({
                    "type": "warning",
                    "message": f"{row.label} averaged {row.avg_actual:.0f}% vs {row.avg_target:.0f}% target",
                    "metric": row.label,
                })
            elif pct >= 95:
                insights.append({
                    "type": "success",
                    "message": f"{row.label} consistently above target ({row.avg_actual:.0f}%)",
                    "metric": row.label,
                })

    # 3. Parse analysis per boss
    rank_query = (
        select(
            Ranking.encounter_name,
            func.avg(Ranking.rank_percent).label("avg_parse"),
            func.count(Ranking.id).label("count"),
        )
        .join(Report, Report.code == Ranking.report_code)
        .where(Ranking.player_id == player.id, Ranking.recorded_at >= cutoff)
    )
    if excluded:
        rank_query = rank_query.where(Report.zone_id.notin_(excluded))
    rankings_result = await db.execute(rank_query.group_by(Ranking.encounter_name))
    for row in rankings_result.all():
        if row.count >= 2 and row.avg_parse < 50:
            insights.append({
                "type": "warning",
                "message": f"Parsed below 50% on {row.encounter_name} (avg {row.avg_parse:.0f}%)",
                "metric": "parse",
            })
        elif row.count >= 2 and row.avg_parse >= 90:
            insights.append({
                "type": "success",
                "message": f"Consistently strong on {row.encounter_name} (avg {row.avg_parse:.0f}%)",
                "metric": "parse",
            })

    # 4. Consumables consistency
    cons_query = (
        select(
            ConsumablesData.label,
            func.avg(ConsumablesData.actual_value).label("avg_actual"),
            func.avg(ConsumablesData.target_value).label("avg_target"),
        )
        .join(Score, (Score.player_id == ConsumablesData.player_id) & (Score.report_code == ConsumablesData.report_code))
        .join(Report, Report.code == ConsumablesData.report_code)
        .where(
            ConsumablesData.player_id == player.id,
            ConsumablesData.optional == False,
            Score.recorded_at >= cutoff,
        )
    )
    if excluded:
        cons_query = cons_query.where(Report.zone_id.notin_(excluded))
    consums_result = await db.execute(cons_query.group_by(ConsumablesData.label))
    for row in consums_result.all():
        if row.avg_target > 0 and row.avg_actual >= row.avg_target:
            insights.append({
                "type": "success",
                "message": f"{row.label} usage consistently at target",
                "metric": row.label,
            })

    if not insights:
        insights.append({
            "type": "info",
            "message": "Not enough data yet to generate insights",
            "metric": None,
        })

    return insights
