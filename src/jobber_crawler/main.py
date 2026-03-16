from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .scheduler.tasks import scheduler, setup_scheduler
from .utils.logging import setup_logging

# Import adapters and mappers so they self-register
from .adapters import greenhouse, linkedin, workday, naukri, indeed  # noqa: F401
from .mappers import greenhouse as _g, linkedin as _l, workday as _w, naukri as _n, indeed as _i  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Jobber Crawler",
    description="Multi-source job crawler with pluggable adapters",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api")
