from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Report, Score, ConsumablesData

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).order_by(Report.start_time.desc()))
    reports = result.scalars().all()
    return [
        {
            "code": r.code,
            "zone_id": r.zone_id,
            "zone_name": r.zone_name,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat(),
            "player_count": len(r.player_names) if r.player_names else 0,
        }
        for r in reports
    ]


@router.get("/{code}")
async def get_report(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.code == code))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    scores_result = await db.execute(
        select(Score).where(Score.report_code == code).order_by(Score.overall_score.desc())
    )
    scores = scores_result.scalars().all()

    consumables_result = await db.execute(
        select(ConsumablesData).where(ConsumablesData.report_code == code)
    )
    consumables = consumables_result.scalars().all()

    return {
        "code": report.code,
        "zone_id": report.zone_id,
        "zone_name": report.zone_name,
        "start_time": report.start_time.isoformat(),
        "end_time": report.end_time.isoformat(),
        "player_names": report.player_names,
        "scores": [
            {
                "player_id": s.player_id,
                "spec": s.spec,
                "overall_score": s.overall_score,
                "parse_score": s.parse_score,
                "utility_score": s.utility_score,
                "consumables_score": s.consumables_score,
            }
            for s in scores
        ],
        "consumables": [
            {
                "player_id": c.player_id,
                "metric_name": c.metric_name,
                "label": c.label,
                "actual_value": c.actual_value,
                "target_value": c.target_value,
                "optional": c.optional,
            }
            for c in consumables
        ],
    }
