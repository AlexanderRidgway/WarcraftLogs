from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, GearSnapshot, AttendanceRecord, ConsumablesData, Score

router = APIRouter(prefix="/api/checklist", tags=["checklist"])


@router.get("")
async def get_checklist(db: AsyncSession = Depends(get_db)):
    players_result = await db.execute(select(Player).order_by(Player.name))
    players = players_result.scalars().all()

    result = []
    for player in players:
        issues = []

        # Check gear: latest snapshot for missing enchants/gems
        latest_report = await db.execute(
            select(GearSnapshot.report_code)
            .where(GearSnapshot.player_id == player.id)
            .order_by(GearSnapshot.recorded_at.desc())
            .limit(1)
        )
        latest_code = latest_report.scalar_one_or_none()

        gear_issues = []
        if latest_code:
            gear_result = await db.execute(
                select(GearSnapshot)
                .where(GearSnapshot.player_id == player.id, GearSnapshot.report_code == latest_code)
            )
            gear = gear_result.scalars().all()

            ENCHANT_SLOTS = {0, 2, 4, 5, 6, 7, 8, 9, 14, 15}  # Head, Shoulder, Chest, Waist, Legs, Feet, Wrist, Hands, Cloak, Weapon
            for item in gear:
                if item.slot in ENCHANT_SLOTS and not item.permanent_enchant:
                    SLOT_NAMES = {0: 'Head', 2: 'Shoulder', 4: 'Chest', 5: 'Waist', 6: 'Legs', 7: 'Feet', 8: 'Wrist', 9: 'Hands', 14: 'Cloak', 15: 'Weapon'}
                    gear_issues.append(f"Missing enchant on {SLOT_NAMES.get(item.slot, f'Slot {item.slot}')}")
                if item.gems:
                    empty = sum(1 for g in item.gems if isinstance(g, dict) and g.get('id', 0) == 0)
                    if empty > 0:
                        gear_issues.append(f"Empty gem socket(s) on Slot {item.slot}")

        # Check attendance: last week
        now = datetime.utcnow()
        iso = now.isocalendar()
        last_week = iso[1] - 1 if iso[1] > 1 else 52
        last_week_year = iso[0] if iso[1] > 1 else iso[0] - 1

        att_result = await db.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.player_id == player.id,
                AttendanceRecord.year == last_week_year,
                AttendanceRecord.week_number == last_week,
            )
        )
        att_records = att_result.scalars().all()
        attendance_missed = any(not a.met for a in att_records) if att_records else False

        # Check consumables: avg over recent reports
        recent_scores = await db.execute(
            select(Score.report_code)
            .where(Score.player_id == player.id)
            .order_by(Score.recorded_at.desc())
            .limit(4)
        )
        recent_codes = [r[0] for r in recent_scores.all()]

        consumables_avg = None
        if recent_codes:
            cons_result = await db.execute(
                select(func.avg(ConsumablesData.actual_value / ConsumablesData.target_value * 100))
                .where(
                    ConsumablesData.player_id == player.id,
                    ConsumablesData.report_code.in_(recent_codes),
                    ConsumablesData.optional == False,
                    ConsumablesData.target_value > 0,
                )
            )
            consumables_avg = cons_result.scalar()
            if consumables_avg is not None:
                consumables_avg = round(consumables_avg, 1)

        # Determine readiness
        if gear_issues or attendance_missed:
            readiness = "red"
        elif consumables_avg is not None and consumables_avg < 80:
            readiness = "yellow"
        else:
            readiness = "green"

        result.append({
            "name": player.name,
            "class_name": player.class_name,
            "readiness": readiness,
            "gear_issues": gear_issues,
            "attendance_missed": attendance_missed,
            "consumables_avg": consumables_avg,
        })

    return {"players": result}
