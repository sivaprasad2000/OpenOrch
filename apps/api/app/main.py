from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.rabbitmq import close_rabbitmq, init_rabbitmq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await init_rabbitmq()
    yield
    await close_rabbitmq()
    await close_db()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Enterprise SaaS Backend API",
        docs_url="/docs",
        redoc_url="/redoc",
        redoc_js_url="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    if settings.STORAGE_BACKEND == "local":
        recordings_path = Path(settings.LOCAL_RECORDINGS_DIR).resolve()
        recordings_path.mkdir(parents=True, exist_ok=True)

        # Serve recording files through a regular FastAPI route so that
        # CORSMiddleware applies. StaticFiles mounts bypass middleware entirely,
        # which causes the Playwright Trace Viewer (trace.playwright.dev) and
        # any cross-origin frontend to be blocked by the browser.
        @app.get("/recordings/{filename}", include_in_schema=False)
        async def serve_recording(filename: str) -> FileResponse:
            # Resolve and validate to prevent path traversal attacks.
            file_path = (recordings_path / filename).resolve()
            try:
                # Ensure the resolved file path is within the recordings directory.
                file_path.relative_to(recordings_path)
            except ValueError:
                # Ensure the resolved path is within the recordings directory.

            if not file_path.is_file():
                raise HTTPException(status_code=404, detail="Recording not found")

                file_path.relative_to(recordings_path)
            except ValueError:
                raise HTTPException(status_code=404, detail="Recording not found")
            if not file_path.is_file():
                raise HTTPException(status_code=404, detail="Recording not found")
            return FileResponse(file_path)

    @app.get("/", tags=["Root"])
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "message": f"Welcome to {settings.APP_NAME}",
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "health": f"{settings.API_V1_PREFIX}/health",
            }
        )

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
