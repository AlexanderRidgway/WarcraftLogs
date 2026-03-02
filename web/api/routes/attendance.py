from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Player, AttendanceRecord

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("")
async def guild_attendance(weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Player.name, Player.class_name, AttendanceRecord)
        .join(AttendanceRecord, AttendanceRecord.player_id == Player.id)
        .where(Player.active == True)
        .order_by(Player.name, AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    rows = result.all()

    players = {}
    for name, class_name, record in rows:
        if name not in players:
            players[name] = {"name": name, "class_name": class_name, "weeks": []}
        players[name]["weeks"].append({
            "year": record.year,
            "week": record.week_number,
            "zone_label": record.zone_label,
            "met": record.met,
        })

    return list(players.values())
