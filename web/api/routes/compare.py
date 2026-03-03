from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from src.config.loader import ConfigLoader
from web.api.database import get_db
from web.api.models import Player, Score, Report

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.get("")
async def compare_spec(
    spec: str = Query(..., description="Spec key like warrior:fury"),
    weeks: int = Query(default=4, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    excluded = ConfigLoader().get_excluded_zones()

    query = (
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.avg(Score.utility_score).label("avg_utility"),
            func.count(Score.id).label("fight_count"),
        )
        .join(Score, Score.player_id == Player.id)
        .join(Report, Report.code == Score.report_code)
        .where(
            Score.spec == spec,
            Score.recorded_at >= cutoff,
        )
    )
    if excluded:
        query = query.where(Report.zone_id.notin_(excluded))
    result = await db.execute(
        query.group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
    )

    return [
        {
            "name": row.name,
            "class_name": row.class_name,
            "avg_score": round(row.avg_score, 1),
            "avg_parse": round(row.avg_parse, 1),
            "avg_utility": round(row.avg_utility, 1) if row.avg_utility else None,
            "fight_count": row.fight_count,
        }
        for row in result.all()
    ]
