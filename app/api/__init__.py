from fastapi import APIRouter

from app.api import teams, players, games, admin, admin_data, admin_cron

api_router = APIRouter()

api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_data.router, tags=["admin-data"])
api_router.include_router(admin_cron.router, tags=["admin-cron"])

