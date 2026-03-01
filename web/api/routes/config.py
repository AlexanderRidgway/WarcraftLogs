from fastapi import APIRouter
from src.config.loader import ConfigLoader

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
