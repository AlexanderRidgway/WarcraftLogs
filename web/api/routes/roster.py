from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score, AttendanceRecord

router = APIRouter(prefix="/api/roster", tags=["roster"])


@router.get("/health")
async def roster_health(weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    # Class/spec distribution from recent scores
    dist_result = await db.execute(
        select(
            Score.spec,
            Player.class_name,
            func.count(func.distinct(Player.id)).label("count"),
        )
        .join(Player, Player.id == Score.player_id)
        .where(Score.recorded_at >= cutoff)
        .group_by(Score.spec, Player.class_name)
    )
    distribution = [
        {"spec": row.spec, "class_name": row.class_name, "count": row.count}
        for row in dist_result.all()
    ]

    # Find at-risk specs (only 1 player)
    at_risk_specs = [d for d in distribution if d["count"] == 1]

    # At-risk players: declining score trend
    at_risk = []
    players_result = await db.execute(select(Player))
    for player in players_result.scalars().all():
        scores_result = await db.execute(
            select(Score)
            .where(Score.player_id == player.id, Score.recorded_at >= cutoff)
            .order_by(Score.recorded_at.asc())
        )
        scores = scores_result.scalars().all()
        if len(scores) >= 4:
            first_half = scores[:len(scores)//2]
            second_half = scores[len(scores)//2:]
            avg_first = sum(s.overall_score for s in first_half) / len(first_half)
            avg_second = sum(s.overall_score for s in second_half) / len(second_half)
            if avg_second - avg_first <= -10:
                at_risk.append({
                    "name": player.name,
                    "class_name": player.class_name,
                    "reason": f"Score declined by {abs(round(avg_second - avg_first, 1))} points",
                })

    # Attendance grid
    att_result = await db.execute(
        select(AttendanceRecord)
        .join(Player, Player.id == AttendanceRecord.player_id)
        .order_by(Player.name, AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    records = att_result.scalars().all()

    # Group by player
    player_att = {}
    player_ids_to_names = {}
    for r in records:
        if r.player_id not in player_att:
            player_att[r.player_id] = []
        player_att[r.player_id].append({
            "year": r.year,
            "week": r.week_number,
            "met": r.met,
        })

    # Get player names
    if player_att:
        names_result = await db.execute(
            select(Player.id, Player.name).where(Player.id.in_(list(player_att.keys())))
        )
        player_ids_to_names = {r.id: r.name for r in names_result.all()}

    attendance_grid = [
        {"name": player_ids_to_names.get(pid, "Unknown"), "weeks": weeks_data[:weeks*3]}
        for pid, weeks_data in player_att.items()
        if pid in player_ids_to_names
    ]

    return {
        "distribution": distribution,
        "at_risk_specs": at_risk_specs,
        "at_risk": at_risk,
        "attendance_grid": sorted(attendance_grid, key=lambda x: x["name"]),
    }
