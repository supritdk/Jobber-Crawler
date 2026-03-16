import asyncio
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.base import ScrapeRequest
from ..adapters.registry import list_adapters
from ..schemas.job import ScrapedJobResponse
from ..services import crawler_service
from ..services.job_store import get_job_count, get_jobs
from .deps import get_db

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "adapters": list_adapters(),
        "active_runs": crawler_service.get_active_runs(),
    }


@router.post("/scrape/trigger/{source}")
async def trigger_scrape(
    source: str,
    keywords: list[str] = Query(default=["software engineer"]),
    location: str | None = Query(default=None),
    max_results: int = Query(default=100, le=5000),
):
    available = list_adapters()
    if source not in available:
        raise HTTPException(404, f"Unknown source: {source}. Available: {available}")

    request = ScrapeRequest(
        keywords=keywords,
        location=location,
        max_results=max_results,
    )

    # Run scrape in background so the API returns immediately
    asyncio.create_task(crawler_service.run_scrape(source, request))

    return {
        "status": "started",
        "source": source,
        "keywords": keywords,
        "location": location,
        "max_results": max_results,
    }


@router.get("/scrape/status")
async def scrape_status():
    return {"active_runs": crawler_service.get_active_runs()}


@router.get("/jobs", response_model=list[ScrapedJobResponse])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    jobs = await get_jobs(db, source=source, limit=limit, offset=offset)
    return jobs


@router.get("/jobs/count")
async def jobs_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    source: str | None = Query(default=None),
):
    count = await get_job_count(db, source=source)
    return {"count": count, "source": source}
