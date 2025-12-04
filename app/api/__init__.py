from fastapi import APIRouter

from app.api import teams, players, admin

api_router = APIRouter()

api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

