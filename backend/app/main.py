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
import logging
import logging.handlers
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .constants import SHELL_VERSION
from .core_client import CatalogueClient, CoreUnavailableError
from .module_loader import load_modules
from .package_cache import PackageCache
from .registry_client import RegistryClient
from .userdb import UserDB

# ---------------------------------------------------------------------------
# Configuration (resolved from environment at startup)
# ---------------------------------------------------------------------------


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
    human-friendly console output (dev).

    In production, logs are also written to ~/.makestack/logs/shell.log
    with 10MB rotation (5 files kept). All output also goes to stdout for Docker.

    BroadcastLogProcessor is inserted before the final renderer so every
    structlog event is fanned out to SSE subscribers (Phase 9).
    """
    from .log_broadcast import BroadcastLogProcessor

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        BroadcastLogProcessor(),  # Fan-out to SSE subscribers before rendering.
    ]
    if dev_mode:
        processors.append(structlog.dev.ConsoleRenderer())
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(10),  # DEBUG
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )
    else:
        processors.append(structlog.processors.JSONRenderer())
        # In production, write JSON logs to file (rotated) AND stdout.
        log_dir = Path.home() / ".makestack" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "shell.log"

        # Set up stdlib logging so structlog can use a rotating file handler.
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        stream_handler = logging.StreamHandler()

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)
        root_logger.setLevel(logging.INFO)

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status code, and duration.

    Emits WARNING for requests that take longer than 1 second.
    Skips health and static-file requests to keep logs clean.
    """

    _SKIP_PREFIXES = ("/health", "/mcp/")

    async def dispatch(self, request: Request, call_next):
        # Skip paths that would produce noisy logs
        path = request.url.path
        for prefix in self._SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        log = structlog.get_logger().bind(component="http")
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        log_fn = log.warning if elapsed_ms > 1000 else log.info
        log_fn(
            "http_request",
            method=request.method,
            path=path,
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return response


# ---------------------------------------------------------------------------
# Background Core health-check
# ---------------------------------------------------------------------------


async def _daily_backup_loop(app: FastAPI) -> None:
    """Run a daily UserDB backup, then prune old backups.

    Sleeps 24 hours between runs. The first backup fires after the initial
    sleep so it doesn't race with the startup sequence. Uses
    asyncio.create_task in the lifespan — never a thread.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    log = structlog.get_logger().bind(component="daily_backup")
    while True:
        await asyncio.sleep(86400)  # 24 hours
        db: UserDB = app.state.userdb
        if db.path == ":memory:":
            continue  # No-op for in-memory DBs (e.g. tests)

        backups_dir = Path(db.path).parent / "backups"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dest = backups_dir / f"userdb-backup-{ts}.sqlite"

        try:
            await db.backup(str(dest))
            deleted = UserDB.prune_backups(backups_dir)
            log.info("daily_backup_complete", path=str(dest), pruned=len(deleted))
        except Exception as exc:
            log.error("daily_backup_failed", error=str(exc))


async def _core_health_poll(app: FastAPI, interval_seconds: int = 30) -> None:
    """Periodically probe Core and update app.state.core_connected."""
    from datetime import datetime, timezone

    log = structlog.get_logger().bind(component="health_poll")
    while True:
        await asyncio.sleep(interval_seconds)
        client: CatalogueClient = app.state.core_client
        was_connected = app.state.core_connected
        now_connected = await client.health_check()
        app.state.core_connected = now_connected
        app.state.last_core_check = datetime.now(timezone.utc).isoformat()

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

    # --- Package manager --------------------------------------------------
    makestack_home = Path(os.getenv("MAKESTACK_HOME", "~/.makestack")).expanduser()
    registry_client = RegistryClient(registries_dir=makestack_home / "registries")
    package_cache = PackageCache(packages_dir=makestack_home / "packages")
    app.state.registry_client = registry_client
    app.state.package_cache = package_cache

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
    from datetime import datetime, timezone

    core_connected = await core_client.health_check()
    app.state.core_client = core_client
    app.state.core_connected = core_connected
    app.state.last_core_check = datetime.now(timezone.utc).isoformat()

    if core_connected:
        log.info("core_connected", url=config["core_url"])
    else:
        log.warning(
            "core_unavailable",
            url=config["core_url"],
            note="Running in degraded mode — catalogue features disabled",
        )

    # --- Module loader ----------------------------------------------------
    # load_modules mounts module routers onto app. Must happen before the
    # server starts accepting requests. Failures are collected, not raised.
    module_registry = await load_modules(app, db)
    app.state.module_registry = module_registry

    loaded = len(module_registry.get_loaded())
    failed = len(module_registry.get_failed())
    if loaded:
        log.info("modules_loaded", count=loaded, failed=failed)
    if failed:
        for fm in module_registry.get_failed():
            log.error("module_failed", name=fm.name, error=fm.error)

    # --- Frontend static files -------------------------------------------
    # Mounted HERE (after load_modules) so module routes are registered first.
    # StaticFiles.matches() always returns Match.FULL, so it must come last in
    # app.routes or it would shadow every route added after create_app() returns.
    # Only active when the built frontend exists (Docker / production).
    import os as _os
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    _frontend_dist = _os.path.join(_os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if _os.path.isdir(_frontend_dist) and not any(
        getattr(r, "name", None) == "frontend" for r in app.routes
    ):
        app.mount("/", _StaticFiles(directory=_frontend_dist, html=True), name="frontend")
        log.info("frontend_static_mounted", path=_frontend_dist)

    # Wire module tools into the MCP server now that the registry is built.
    try:
        from mcp_server.transport import get_mcp_server
        from mcp_server.tool_generator import generate_module_tools

        mcp = get_mcp_server()
        registered = await generate_module_tools(mcp, module_registry)
        if registered:
            log.info("mcp_module_tools_registered", count=registered)
    except Exception as exc:
        log.warning("mcp_module_tools_failed", error=str(exc))

    # --- Background tasks -------------------------------------------------
    health_task = asyncio.create_task(_core_health_poll(app))
    backup_task = asyncio.create_task(_daily_backup_loop(app))

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
        modules_loaded=loaded,
        modules_failed=failed,
    )
    print(
        f"\nMakestack Shell v{SHELL_VERSION}\n"
        f"Core: {'connected' if core_connected else 'unavailable (degraded mode)'}"
        f" ({config['core_url']})\n"
        f"UserDB: {userdb_display}\n"
        f"Modules: {loaded} loaded"
        + (f", {failed} failed" if failed else "")
        + f"\nDev mode: {'enabled' if config['dev_mode'] else 'disabled'}\n"
        f"Listening on http://localhost:{config['port']}\n"
    )

    yield  # Application runs here

    # --- Shutdown ---------------------------------------------------------
    health_task.cancel()
    backup_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    try:
        await backup_task
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
    from .routers import backups, catalogue, data, dev, inventory, mcp_log, modules, packages, settings, system, terminal, users, version, workshops

    app = FastAPI(
        title="Makestack Shell",
        version=SHELL_VERSION,
        description=(
            "The Makestack Shell API — proxy to the catalogue engine, "
            "personal inventory and workshop management, module host."
        ),
        lifespan=lifespan,
    )

    # Request logging middleware — must be added before CORS so it sees all requests.
    app.add_middleware(RequestLoggingMiddleware)

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
    app.include_router(users.router)
    app.include_router(modules.router)
    app.include_router(packages.router)
    app.include_router(data.router)
    app.include_router(system.router)
    app.include_router(backups.router)    # Always available — backup infrastructure (Phase 10).
    app.include_router(mcp_log.router)    # Always available — core audit infrastructure.
    app.include_router(terminal.router)   # Always available — terminal + log stream (Phase 9).
    app.include_router(dev.router)  # Only active in dev mode; the router self-guards.

    # Mount MCP SSE endpoint at /mcp — AI agents connect here.
    # The SSE endpoint is available at /mcp/sse.
    from mcp_server.transport import create_sse_app
    app.mount("/mcp", create_sse_app())

    # NOTE: The frontend StaticFiles mount is intentionally NOT added here.
    # It must be added AFTER load_modules() in the lifespan so that module
    # routes (which are added during lifespan startup) are registered before
    # the catch-all StaticFiles Mount. StaticFiles.matches() always returns
    # Match.FULL, so it would shadow any routes added after it in app.routes.

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
