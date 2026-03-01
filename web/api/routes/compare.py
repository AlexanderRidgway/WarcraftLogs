from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.get("")
async def compare_spec(
    spec: str = Query(..., description="Spec key like warrior:fury"),
    weeks: int = Query(default=4, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.avg(Score.utility_score).label("avg_utility"),
            func.count(Score.id).label("fight_count"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(
            Score.spec == spec,
            Score.recorded_at >= cutoff,
        )
        .group_by(Player.name, Player.class_name)
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
