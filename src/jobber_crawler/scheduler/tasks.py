import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..adapters.base import ScrapeRequest
from ..adapters.registry import list_adapters
from ..config import settings
from ..services.crawler_service import run_scrape

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

# Default scrape configurations per source
DEFAULT_SCHEDULES = {
    "greenhouse": {"cron": "0 */6 * * *", "keywords": ["software engineer"]},
    "linkedin": {"cron": "0 */4 * * *", "keywords": ["software engineer"]},
    "workday": {"cron": "0 8 * * *", "keywords": ["software engineer"]},
    "naukri": {"cron": "0 */6 * * *", "keywords": ["software engineer"]},
    "indeed": {"cron": "30 */4 * * *", "keywords": ["software engineer"]},
}


async def _run_scheduled_scrape(source: str, keywords: list[str]) -> None:
    logger.info("scheduled_scrape_triggered", source=source)
    request = ScrapeRequest(keywords=keywords, max_results=1000)
    await run_scrape(source, request)


def setup_scheduler() -> None:
    """Register scheduled jobs for all enabled adapters."""
    available = list_adapters()

    for source, config in DEFAULT_SCHEDULES.items():
        if source not in available:
            continue

        # Check if source is enabled in settings
        enabled_attr = f"{source}_enabled"
        if hasattr(settings, enabled_attr) and not getattr(settings, enabled_attr):
            logger.info("source_disabled", source=source)
            continue

        cron_parts = config["cron"].split()
        scheduler.add_job(
            _run_scheduled_scrape,
            "cron",
            args=[source, config["keywords"]],
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2] if cron_parts[2] != "*" else None,
            month=cron_parts[3] if cron_parts[3] != "*" else None,
            day_of_week=cron_parts[4] if cron_parts[4] != "*" else None,
            id=f"scrape_{source}",
            replace_existing=True,
        )
        logger.info("scheduled_job_added", source=source, cron=config["cron"])
