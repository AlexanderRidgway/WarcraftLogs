from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes.players import router as players_router
from web.api.routes.reports import router as reports_router
from web.api.routes.leaderboard import router as leaderboard_router
from web.api.routes.attendance import router as attendance_router
from web.api.routes.config import router as config_router
from web.api.routes.sync_status import router as sync_status_router
from web.api.routes.auth import router as auth_router
from web.api.routes.mvp import router as mvp_router
from web.api.routes.insights import router as insights_router

app = FastAPI(title="CRANK Guild Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(reports_router)
app.include_router(leaderboard_router)
app.include_router(attendance_router)
app.include_router(config_router)
app.include_router(sync_status_router)
app.include_router(auth_router)
app.include_router(mvp_router)
app.include_router(insights_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


import os
from fastapi.staticfiles import StaticFiles

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
