from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import engine
from app.core.errors import error_response_docs, setup_exception_handlers
from app.modules.experience.api import router as experience_router
from app.modules.health.api import router as health_router
from app.modules.skills.api import router as skills_router
from app.modules.tailoring.api import router as tailoring_router
from app.settings import Settings, get_settings

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def setup_routing(app: FastAPI) -> None:
    app.include_router(health_router)

    api_v1 = APIRouter(prefix=API_V1_PREFIX, responses=error_response_docs(500))
    api_v1.include_router(skills_router)
    api_v1.include_router(experience_router)
    api_v1.include_router(tailoring_router)
    app.include_router(api_v1)


def setup_middlewares(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def app_factory(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="CVariant API",
        description="Generate CV variants tailored to a specific job offer.",
        version=settings.VERSION,
        root_path=settings.API_ROOT_PATH,
        lifespan=lifespan,
    )
    setup_routing(app)
    setup_middlewares(app, settings)
    setup_exception_handlers(app)
    return app
