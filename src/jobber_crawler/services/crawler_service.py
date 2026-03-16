from datetime import datetime, timezone

import structlog

from ..adapters.base import ScrapeRequest
from ..adapters.registry import get_adapter, get_mapper
from ..database import async_session
from ..schemas.job import ScrapedJobCreate
from .job_store import upsert_jobs

logger = structlog.get_logger()

# Track active scrape runs
_active_runs: dict[str, dict] = {}


async def run_scrape(source: str, request: ScrapeRequest) -> dict:
    """Run a scrape for a given source. Orchestrates: adapter -> mapper -> DB upsert."""
    log = logger.bind(source=source)

    if source in _active_runs:
        log.warning("scrape_already_running")
        return {"status": "already_running", "source": source}

    _active_runs[source] = {"started_at": datetime.now(timezone.utc)}

    try:
        adapter = get_adapter(source)
        mapper = get_mapper(source)

        log.info("scrape_started", keywords=request.keywords, location=request.location)

        jobs: list[ScrapedJobCreate] = []
        count = 0

        async for raw_job in adapter.scrape(request):
            try:
                mapped = mapper.map(raw_job)
                jobs.append(mapped)
                count += 1

                # Batch upsert every 50 jobs to avoid memory buildup
                if len(jobs) >= 50:
                    async with async_session() as session:
                        await upsert_jobs(session, jobs)
                    jobs.clear()

            except Exception:
                log.exception("mapping_error", external_id=raw_job.external_id)
                continue

            if count >= request.max_results:
                break

        # Upsert remaining jobs
        if jobs:
            async with async_session() as session:
                await upsert_jobs(session, jobs)

        log.info("scrape_completed", total_jobs=count)
        return {"status": "completed", "source": source, "jobs_scraped": count}

    except Exception:
        log.exception("scrape_failed")
        return {"status": "failed", "source": source, "error": "See logs for details"}

    finally:
        _active_runs.pop(source, None)


def get_active_runs() -> dict[str, dict]:
    return dict(_active_runs)
