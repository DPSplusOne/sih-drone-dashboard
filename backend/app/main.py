"""FastAPI application entry point for AeroTrace 3D."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .logging_config import configure_logging
from .routers import health, jobs


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application with local-development defaults."""

    application_settings = settings or get_settings()
    logger = configure_logging(application_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        application_settings.ensure_directories()
        app.state.settings = application_settings
        logger.info(
            "application_started",
            extra={
                "event": "application_started",
                "data_dir": application_settings.data_dir,
                "jobs_dir": application_settings.jobs_dir,
                "output_dir": application_settings.output_dir,
            },
        )
        yield
        logger.info("application_stopped", extra={"event": "application_stopped"})

    app = FastAPI(
        title="AeroTrace 3D API",
        version="0.1.0",
        description="Local development API for the AeroTrace 3D reconstruction pipeline.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(application_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.warning(
                "http_request_failed",
                extra={
                    "event": "http_request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            raise

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request_completed",
            extra={
                "event": "http_request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "request_validation_failed",
            extra={
                "event": "request_validation_failed",
                "request_id": request_id,
                "path": request.url.path,
                "errors": exc.errors(),
            },
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "Request validation failed", "request_id": request_id, "errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "unhandled_exception",
            extra={"event": "unhandled_exception", "request_id": request_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    app.include_router(health.router)
    app.include_router(jobs.router)
    return app


app = create_app()
