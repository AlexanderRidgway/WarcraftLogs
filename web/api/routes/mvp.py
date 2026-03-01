from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/mvp", tags=["mvp"])


@router.get("")
async def get_mvp(weeks_ago: int = Query(default=0, ge=0, le=8), db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    today = now.date()
    # ISO week: Monday-Sunday
    start_of_week = today - timedelta(days=today.weekday() + (weeks_ago * 7))
    end_of_week = start_of_week + timedelta(days=7)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.avg(Score.utility_score).label("avg_utility"),
            func.avg(Score.consumables_score).label("avg_consumables"),
            func.count(Score.id).label("fight_count"),
            func.max(Score.spec).label("spec"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(
            Score.recorded_at >= datetime.combine(start_of_week, datetime.min.time()),
            Score.recorded_at < datetime.combine(end_of_week, datetime.min.time()),
        )
        .group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None

    return {
        "name": row.name,
        "class_name": row.class_name,
        "spec": row.spec,
        "overall_score": round(row.avg_score, 1),
        "parse_score": round(row.avg_parse, 1),
        "utility_score": round(row.avg_utility, 1) if row.avg_utility else None,
        "consumables_score": round(row.avg_consumables, 1) if row.avg_consumables else None,
        "fight_count": row.fight_count,
        "week_start": start_of_week.isoformat(),
    }
