"""Top-level API router; route modules are included here under the `/api` prefix."""

from fastapi import APIRouter

from app.api.routes import (
    applications,
    dashboard,
    health,
    interview,
    jobs,
    profile,
    recommendations,
    resume,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(profile.router)
api_router.include_router(jobs.router)
api_router.include_router(recommendations.router)
api_router.include_router(applications.router)
api_router.include_router(dashboard.router)
api_router.include_router(resume.router)
api_router.include_router(interview.router)
