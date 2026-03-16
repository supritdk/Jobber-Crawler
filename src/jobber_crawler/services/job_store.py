from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scraped_job import ScrapedJob
from ..schemas.job import ScrapedJobCreate

logger = structlog.get_logger()

_UPDATE_FIELDS = [
    "title", "company_name", "description_text", "apply_url", "source_url",
    "location", "salary", "salary_info", "employment_type", "seniority_level",
    "is_easy_apply", "company_website", "company_logo", "industries",
    "job_function", "benefits", "posted_at", "applicants_count", "category",
]


def _build_upsert(dialect_name: str):
    """Return the dialect-appropriate insert function."""
    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy.dialects.postgresql import insert
    return insert


async def upsert_jobs(session: AsyncSession, jobs: list[ScrapedJobCreate]) -> dict:
    """Upsert jobs using ON CONFLICT (external_id, source) DO UPDATE."""
    if not jobs:
        return {"upserted": 0}

    dialect_name = session.bind.dialect.name if session.bind else "postgresql"
    insert = _build_upsert(dialect_name)
    now = datetime.now(timezone.utc)

    for job in jobs:
        values = job.model_dump()
        values["synced_at"] = now

        stmt = insert(ScrapedJob).values(**values)
        update_set = {field: stmt.excluded[field] for field in _UPDATE_FIELDS}
        update_set["synced_at"] = now
        update_set["updated_at"] = now

        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id", "source"],
            set_=update_set,
        )

        await session.execute(stmt)

    await session.commit()

    logger.info("upsert_complete", count=len(jobs), source=jobs[0].source if jobs else "unknown")
    return {"upserted": len(jobs)}


async def get_jobs(
    session: AsyncSession,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ScrapedJob]:
    """Query jobs with optional source filter."""
    stmt = select(ScrapedJob).where(ScrapedJob.deleted_at.is_(None))
    if source:
        stmt = stmt.where(ScrapedJob.source == source)
    stmt = stmt.order_by(ScrapedJob.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_job_count(session: AsyncSession, source: str | None = None) -> int:
    """Count active (non-deleted) jobs."""
    from sqlalchemy import func

    stmt = select(func.count(ScrapedJob.id)).where(ScrapedJob.deleted_at.is_(None))
    if source:
        stmt = stmt.where(ScrapedJob.source == source)
    result = await session.execute(stmt)
    return result.scalar() or 0
