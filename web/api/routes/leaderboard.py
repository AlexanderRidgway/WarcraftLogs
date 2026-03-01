from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.count(Score.id).label("fight_count"),
            func.max(Score.spec).label("spec"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(Score.recorded_at >= cutoff)
        .group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
    )
    rows = result.all()

    return [
        {
            "rank": i + 1,
            "name": r.name,
            "class_name": r.class_name,
            "spec": r.spec,
            "avg_score": round(r.avg_score, 1),
            "avg_parse": round(r.avg_parse, 1),
            "fight_count": r.fight_count,
        }
        for i, r in enumerate(rows)
    ]
