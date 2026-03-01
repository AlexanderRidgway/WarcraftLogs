from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.config.loader import ConfigLoader
from web.api.auth import get_current_officer
from web.api.models import User

router = APIRouter(prefix="/api/config", tags=["config"])

config = ConfigLoader()


@router.get("/specs")
async def get_specs():
    specs = config.all_specs()
    return {
        spec_key: config.get_spec(spec_key)
        for spec_key in specs
    }


@router.get("/consumables")
async def get_consumables():
    return config.get_consumables()


@router.get("/attendance")
async def get_attendance():
    return config.get_attendance()


@router.get("/gear")
async def get_gear():
    return config.get_gear_check()


class UpdateTargetRequest(BaseModel):
    target: int


@router.put("/specs/{spec_key}/contributions/{metric}")
async def update_spec_target(spec_key: str, metric: str, body: UpdateTargetRequest, officer: User = Depends(get_current_officer)):
    try:
        config.update_target(spec_key, metric, body.target)
        return {"status": "ok", "spec_key": spec_key, "metric": metric, "target": body.target}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class UpdateWeightsRequest(BaseModel):
    parse_weight: float
    utility_weight: float
    consumables_weight: float


@router.put("/specs/{spec_key}/weights")
async def update_spec_weights(spec_key: str, body: UpdateWeightsRequest, officer: User = Depends(get_current_officer)):
    profile = config.get_spec(spec_key)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_key}' not found")
    total = body.parse_weight + body.utility_weight + body.consumables_weight
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total:.2f}")
    profile["parse_weight"] = body.parse_weight
    profile["utility_weight"] = body.utility_weight
    profile["consumables_weight"] = body.consumables_weight
    config._save()
    return {"status": "ok", "spec_key": spec_key}


class UpdateAttendanceRequest(BaseModel):
    required_per_week: int


@router.put("/attendance/{zone_id}")
async def update_attendance_zone(zone_id: int, body: UpdateAttendanceRequest, officer: User = Depends(get_current_officer)):
    try:
        config.update_attendance_zone(zone_id, body.required_per_week)
        return {"status": "ok", "zone_id": zone_id, "required_per_week": body.required_per_week}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
