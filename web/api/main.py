from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes.players import router as players_router
from web.api.routes.reports import router as reports_router
from web.api.routes.leaderboard import router as leaderboard_router
from web.api.routes.attendance import router as attendance_router
from web.api.routes.config import router as config_router
from web.api.routes.sync_status import router as sync_status_router

app = FastAPI(title="CRANK Guild Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(reports_router)
app.include_router(leaderboard_router)
app.include_router(attendance_router)
app.include_router(config_router)
app.include_router(sync_status_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
