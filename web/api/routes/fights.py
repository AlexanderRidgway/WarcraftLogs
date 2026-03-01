from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Fight, Death, Player

router = APIRouter(prefix="/api/reports", tags=["fights"])


@router.get("/{code}/deaths")
async def get_report_deaths(code: str, db: AsyncSession = Depends(get_db)):
    # Get all fights for this report
    fights_result = await db.execute(
        select(Fight).where(Fight.report_code == code).order_by(Fight.start_time)
    )
    fights = fights_result.scalars().all()

    per_fight = []
    death_totals: dict[str, dict] = {}

    for fight in fights:
        deaths_result = await db.execute(
            select(Death, Player.name, Player.class_name)
            .join(Player, Player.id == Death.player_id)
            .where(Death.fight_db_id == fight.id)
            .order_by(Death.timestamp_ms)
        )

        fight_deaths = []
        for death, player_name, class_name in deaths_result.all():
            timestamp_pct = round((death.timestamp_ms / fight.duration_ms) * 100, 1) if fight.duration_ms > 0 else 0
            fight_deaths.append({
                "player": player_name,
                "class_name": class_name,
                "timestamp_pct": timestamp_pct,
                "ability": death.killing_ability or "Unknown",
            })
            if player_name not in death_totals:
                death_totals[player_name] = {"player": player_name, "class_name": class_name, "death_count": 0}
            death_totals[player_name]["death_count"] += 1

        per_fight.append({
            "fight_name": fight.encounter_name,
            "kill": fight.kill,
            "deaths": fight_deaths,
        })

    totals = sorted(death_totals.values(), key=lambda x: x["death_count"], reverse=True)

    return {"per_fight": per_fight, "totals": totals}


@router.get("/{code}/wipes")
async def get_report_wipes(code: str, db: AsyncSession = Depends(get_db)):
    fights_result = await db.execute(
        select(Fight).where(Fight.report_code == code).order_by(Fight.encounter_name, Fight.start_time)
    )
    fights = fights_result.scalars().all()

    # Group by encounter
    encounters: dict[str, dict] = {}
    for fight in fights:
        if fight.encounter_name not in encounters:
            encounters[fight.encounter_name] = {
                "encounter_name": fight.encounter_name,
                "wipe_count": 0,
                "kill_count": 0,
                "wipes": [],
            }

        if fight.kill:
            encounters[fight.encounter_name]["kill_count"] += 1
        else:
            encounters[fight.encounter_name]["wipe_count"] += 1

            # Get deaths for this wipe
            deaths_result = await db.execute(
                select(Death, Player.name)
                .join(Player, Player.id == Death.player_id)
                .where(Death.fight_db_id == fight.id)
                .order_by(Death.timestamp_ms)
            )
            wipe_deaths = []
            for death, player_name in deaths_result.all():
                timestamp_pct = round((death.timestamp_ms / fight.duration_ms) * 100, 1) if fight.duration_ms > 0 else 0
                wipe_deaths.append({
                    "player": player_name,
                    "timestamp_pct": timestamp_pct,
                    "ability": death.killing_ability or "Unknown",
                })

            encounters[fight.encounter_name]["wipes"].append({
                "fight_id": fight.fight_id,
                "duration_s": round(fight.duration_ms / 1000),
                "boss_pct": fight.fight_percentage,
                "deaths": wipe_deaths,
            })

    # Only return encounters that have wipes
    return [e for e in encounters.values() if e["wipe_count"] > 0]
