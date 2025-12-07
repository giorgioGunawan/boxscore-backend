"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.cache import close_redis
from app.api import api_router
from app.api.admin import set_templates
from app.config import get_settings
from app.cron import start_scheduler, stop_scheduler

# Reduce SQLAlchemy logging noise
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

settings = get_settings()

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("🏀 Starting NBA Boxscore Backend...")
    await init_db()
    print("✅ Database initialized")
    
    # Initialize cron jobs in DB
    from app.cron.scheduler import initialize_cron_jobs
    await initialize_cron_jobs()
    
    # Start cron scheduler
    start_scheduler()
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    stop_scheduler()
    await close_redis()
    print("✅ Redis connection closed")


app = FastAPI(
    title="NBA Boxscore Backend",
    description="Backend API for NBA widget data - schedules, standings, player stats",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Set up templates
if TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    set_templates(templates)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "NBA Boxscore Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "admin": "/api/admin/",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

