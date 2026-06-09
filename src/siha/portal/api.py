"""FastAPI backend with REST + SSE + auth."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from siha.config import settings
from siha.portal.routers import sessions, harness, mutations, benchmarks, tools, run, stream, improve

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global _scheduler
    from siha.harness.scheduler import Scheduler

    _scheduler = Scheduler()
    _scheduler.start()
    yield
    if _scheduler is not None:
        _scheduler.stop()


app = FastAPI(title="SIHA Portal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include all routers
app.include_router(sessions.router)
app.include_router(harness.router)
app.include_router(mutations.router)
app.include_router(benchmarks.router)
app.include_router(tools.router)
app.include_router(run.router)
app.include_router(stream.router)
app.include_router(improve.router)
