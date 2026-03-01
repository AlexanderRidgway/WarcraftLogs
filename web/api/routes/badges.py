from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Player, Badge
from web.api.badges import BADGE_DEFINITIONS

router = APIRouter(tags=["badges"])


@router.get("/api/players/{name}/badges")
async def get_player_badges(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    badges_result = await db.execute(
        select(Badge)
        .where(Badge.player_id == player.id)
        .order_by(Badge.earned_at.desc())
    )
    badges = badges_result.scalars().all()

    return [
        {
            "badge_type": b.badge_type,
            "earned_at": b.earned_at.isoformat() if b.earned_at else None,
            "details": b.details,
            "label": next((d["label"] for d in BADGE_DEFINITIONS if d["type"] == b.badge_type), b.badge_type),
            "description": next((d["description"] for d in BADGE_DEFINITIONS if d["type"] == b.badge_type), ""),
        }
        for b in badges
    ]


@router.get("/api/achievements")
async def get_all_achievements(db: AsyncSession = Depends(get_db)):
    # Get badge counts
    counts_result = await db.execute(
        select(Badge.badge_type, func.count(Badge.id).label("count"))
        .group_by(Badge.badge_type)
    )
    badge_counts = {row.badge_type: row.count for row in counts_result.all()}

    # Get recent earners
    result = []
    for defn in BADGE_DEFINITIONS:
        recent_result = await db.execute(
            select(Badge, Player.name)
            .join(Player, Player.id == Badge.player_id)
            .where(Badge.badge_type == defn["type"])
            .order_by(Badge.earned_at.desc())
            .limit(5)
        )
        earners = [{"name": name, "details": b.details, "earned_at": b.earned_at.isoformat() if b.earned_at else None}
                    for b, name in recent_result.all()]

        result.append({
            "type": defn["type"],
            "label": defn["label"],
            "description": defn["description"],
            "count": badge_counts.get(defn["type"], 0),
            "recent_earners": earners,
        })

    return result
