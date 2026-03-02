from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score, Report

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(
    weeks: int = Query(default=4, ge=1, le=52),
    sort_by: str = Query(default="parse"),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    order_col = func.avg(Score.parse_score) if sort_by == "parse" else func.avg(Score.overall_score)

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
        .where(Score.recorded_at >= cutoff, Player.active == True)
        .group_by(Player.name, Player.class_name)
        .order_by(order_col.desc())
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


@router.get("/guild-trends")
async def guild_trends(
    weeks: int = Query(default=8, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    """Average guild parse and score per report over time."""
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    result = await db.execute(
        select(
            Score.report_code,
            Report.start_time,
            func.avg(Score.parse_score).label("avg_parse"),
            func.avg(Score.overall_score).label("avg_score"),
            func.count(Score.id).label("player_count"),
        )
        .join(Report, Report.code == Score.report_code)
        .where(Report.start_time >= cutoff)
        .group_by(Score.report_code, Report.start_time)
        .order_by(Report.start_time.asc())
    )
    rows = result.all()

    return [
        {
            "date": r.start_time.isoformat(),
            "report_code": r.report_code,
            "avg_parse": round(r.avg_parse, 1),
            "avg_score": round(r.avg_score, 1),
            "player_count": r.player_count,
        }
        for r in rows
    ]
