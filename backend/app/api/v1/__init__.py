from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.circles import router as circles_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.intents import router as intents_router
from app.api.v1.match import router as match_router
from app.api.v1.public import router as public_router
from app.api.v1.relationships import router as relationships_router
from app.api.v1.reports import router as reports_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.verifications import router as verifications_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, tags=["system"])
api_v1_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_v1_router.include_router(relationships_router, prefix="/relationships", tags=["relationships"])
api_v1_router.include_router(circles_router, prefix="/circles", tags=["circles"])
api_v1_router.include_router(intents_router, prefix="/intents", tags=["intents"])
api_v1_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_v1_router.include_router(match_router, prefix="/match", tags=["match"])
api_v1_router.include_router(verifications_router, prefix="/verifications", tags=["verifications"])
api_v1_router.include_router(reports_router, tags=["reports"])
api_v1_router.include_router(public_router, prefix="/public", tags=["public"])
api_v1_router.include_router(events_router, prefix="/events", tags=["events"])
