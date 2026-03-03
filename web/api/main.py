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
from web.api.routes.checklist import router as checklist_router
from web.api.routes.compare import router as compare_router
from web.api.routes.roster import router as roster_router
from web.api.routes.fights import router as fights_router
from web.api.routes.badges import router as badges_router
from web.api.routes.weekly import router as weekly_router

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
app.include_router(checklist_router)
app.include_router(compare_router)
app.include_router(roster_router)
app.include_router(fights_router)
app.include_router(badges_router)
app.include_router(weekly_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(static_dir):
    # Mount /assets for Vite-built JS/CSS bundles (correct MIME types)
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Catch-all: serve static file if it exists, otherwise index.html (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path:
            file_path = os.path.join(static_dir, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
        return FileResponse(os.path.join(static_dir, "index.html"), media_type="text/html")
