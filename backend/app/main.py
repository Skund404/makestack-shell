"""Makestack Shell — FastAPI application entry point.

Startup sequence:
  1. Load config from environment variables
  2. Configure structlog
  3. Open UserDB and run Shell core migrations
  4. Attempt Core connection (log warning if unavailable — degraded mode)
  5. Mount all routers
  6. Start background Core health-check polling
  7. Log startup summary
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core_client import CatalogueClient, CoreUnavailableError
from .userdb import UserDB

# ---------------------------------------------------------------------------
# Configuration (resolved from environment at startup)
# ---------------------------------------------------------------------------

SHELL_VERSION = "0.1.0"


def _load_config() -> dict:
    """Read all configuration from environment variables."""
    return {
        "core_url": os.getenv("MAKESTACK_CORE_URL", "http://localhost:8420"),
        "core_api_key": os.getenv("MAKESTACK_CORE_API_KEY", ""),
        "userdb_path": os.getenv("MAKESTACK_USERDB_PATH", "~/.makestack/userdb.sqlite"),
        "dev_mode": os.getenv("MAKESTACK_DEV_MODE", "false").lower() in ("true", "1", "yes"),
        "port": int(os.getenv("MAKESTACK_PORT", "3000")),
    }


# ---------------------------------------------------------------------------
# Structlog setup
# ---------------------------------------------------------------------------


def _configure_logging(dev_mode: bool) -> None:
    """Configure structlog for structured JSON output (production) or
    human-friendly console output (dev)."""
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if dev_mode:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            20 if not dev_mode else 10  # INFO in prod, DEBUG in dev
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


# ---------------------------------------------------------------------------
# Background Core health-check
# ---------------------------------------------------------------------------


async def _core_health_poll(app: FastAPI, interval_seconds: int = 30) -> None:
    """Periodically probe Core and update app.state.core_connected."""
    log = structlog.get_logger().bind(component="health_poll")
    while True:
        await asyncio.sleep(interval_seconds)
        client: CatalogueClient = app.state.core_client
        was_connected = app.state.core_connected
        now_connected = await client.health_check()
        app.state.core_connected = now_connected

        if was_connected and not now_connected:
            log.warning("core_disconnected")
        elif not was_connected and now_connected:
            log.info("core_reconnected")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs startup then yields, then runs shutdown."""
    config = _load_config()
    _configure_logging(config["dev_mode"])
    log = structlog.get_logger().bind(component="startup")

    # Store config on app state so routers can read it.
    app.state.config = config
    app.state.dev_mode = config["dev_mode"]
    app.state.start_time = time.monotonic()

    # --- UserDB -----------------------------------------------------------
    db = UserDB(path=config["userdb_path"], dev_mode=config["dev_mode"])
    await db.open()
    await db.run_migrations()
    app.state.userdb = db

    # --- Core connection --------------------------------------------------
    core_client = CatalogueClient(
        base_url=config["core_url"],
        api_key=config["core_api_key"],
        dev_mode=config["dev_mode"],
    )
    core_connected = await core_client.health_check()
    app.state.core_client = core_client
    app.state.core_connected = core_connected

    if core_connected:
        log.info("core_connected", url=config["core_url"])
    else:
        log.warning(
            "core_unavailable",
            url=config["core_url"],
            note="Running in degraded mode — catalogue features disabled",
        )

    # --- Background tasks -------------------------------------------------
    health_task = asyncio.create_task(_core_health_poll(app))

    # --- Startup summary --------------------------------------------------
    userdb_display = Path(config["userdb_path"]).expanduser()
    log.info(
        "shell_started",
        version=SHELL_VERSION,
        core_connected=core_connected,
        core_url=config["core_url"],
        userdb=str(userdb_display),
        dev_mode=config["dev_mode"],
        port=config["port"],
    )
    print(
        f"\nMakestack Shell v{SHELL_VERSION}\n"
        f"Core: {'connected' if core_connected else 'unavailable (degraded mode)'}"
        f" ({config['core_url']})\n"
        f"UserDB: {userdb_display}\n"
        f"Dev mode: {'enabled' if config['dev_mode'] else 'disabled'}\n"
        f"Listening on http://localhost:{config['port']}\n"
    )

    yield  # Application runs here

    # --- Shutdown ---------------------------------------------------------
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    await core_client.close()
    await db.close()
    log.info("shell_stopped")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Separated from module-level code so tests can call create_app() with
    their own overrides before importing.
    """
    # Import routers here to avoid circular imports at module load time.
    from .routers import catalogue, dev, inventory, modules, settings, system, version, workshops

    app = FastAPI(
        title="Makestack Shell",
        version=SHELL_VERSION,
        description=(
            "The Makestack Shell API — proxy to the catalogue engine, "
            "personal inventory and workshop management, module host."
        ),
        lifespan=lifespan,
    )

    # CORS: allow the React dev server (localhost:5173) during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",   # Vite dev server
            "http://localhost:3000",   # Shell itself (same-origin)
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global error handler — gives AI-friendly error messages for unhandled exceptions.
    @app.exception_handler(Exception)
    async def _global_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log = structlog.get_logger().bind(component="error_handler")
        log.error("unhandled_exception", path=str(request.url.path), error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "path": str(request.url.path),
                "suggestion": "Check Shell logs for a full traceback.",
            },
        )

    # Mount routers.
    app.include_router(catalogue.router)
    app.include_router(inventory.router)
    app.include_router(workshops.router)
    app.include_router(version.router)
    app.include_router(settings.router)
    app.include_router(modules.router)
    app.include_router(system.router)
    app.include_router(dev.router)  # Only active in dev mode; the router self-guards.

    return app


# Module-level app instance used by uvicorn and tests.
app = create_app()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Shell from the command line."""
    config = _load_config()
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=config["port"],
        reload=config["dev_mode"],
        log_config=None,  # Let structlog handle logging.
    )


if __name__ == "__main__":
    main()
