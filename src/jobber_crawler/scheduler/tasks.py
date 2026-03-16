import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..adapters.base import ScrapeRequest
from ..adapters.registry import list_adapters
from ..config import settings
from ..services.crawler_service import run_scrape

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

# Cron schedule per source (timing only — keywords/locations come from settings)
SOURCE_SCHEDULES = {
    "greenhouse": "0 */6 * * *",
    "linkedin": "0 */4 * * *",
    "workday": "0 8 * * *",
    "naukri": "0 */6 * * *",
    "indeed": "30 */4 * * *",
}


async def _run_scheduled_scrape(source: str) -> None:
    """Run a scrape for all configured roles × locations for the given source."""
    roles = settings.get_scrape_roles()
    locations = settings.get_scrape_locations()

    for role in roles:
        for loc in locations:
            city = loc["city"]
            country = loc["country"]
            location_str = f"{city}, {country}".strip(", ") if city or country else None

            log = logger.bind(source=source, role=role, location=location_str)
            log.info("scheduled_scrape_triggered")

            request = ScrapeRequest(
                keywords=[role],
                location=location_str,
                max_results=settings.scrape_max_results,
                posted_within_hours=settings.scrape_freshness_hours or None,
            )
            await run_scrape(source, request)


def setup_scheduler() -> None:
    """Register scheduled jobs for all configured and enabled sources."""
    available = list_adapters()
    configured_sources = settings.get_scrape_sources()

    for source in configured_sources:
        if source not in available:
            logger.warning("configured_source_not_available", source=source)
            continue

        enabled_attr = f"{source}_enabled"
        if hasattr(settings, enabled_attr) and not getattr(settings, enabled_attr):
            logger.info("source_disabled", source=source)
            continue

        cron = SOURCE_SCHEDULES.get(source, "0 */6 * * *")
        cron_parts = cron.split()
        scheduler.add_job(
            _run_scheduled_scrape,
            "cron",
            args=[source],
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2] if cron_parts[2] != "*" else None,
            month=cron_parts[3] if cron_parts[3] != "*" else None,
            day_of_week=cron_parts[4] if cron_parts[4] != "*" else None,
            id=f"scrape_{source}",
            replace_existing=True,
        )
        logger.info("scheduled_job_added", source=source, cron=cron)
