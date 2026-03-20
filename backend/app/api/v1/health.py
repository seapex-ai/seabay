from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "region": settings.REGION,
    }


@router.get("/health/detail")
async def health_detail(db: AsyncSession = Depends(get_db)):
    """Detailed health check with DB and Redis status."""
    components = {}

    # Check PostgreSQL
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        components["database"] = {"status": "ok", "type": "postgresql"}
    except Exception as e:
        components["database"] = {"status": "down", "error": str(e)}

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await r.ping()
        await r.aclose()
        components["redis"] = {"status": "ok" if pong else "down"}
    except Exception as e:
        components["redis"] = {"status": "down", "error": str(e)}

    # API always ok if we got here
    components["api"] = {"status": "ok", "version": settings.APP_VERSION}

    all_ok = all(c["status"] == "ok" for c in components.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "region": settings.REGION,
        "components": components,
    }
