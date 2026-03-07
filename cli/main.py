"""makestack — Makestack Shell CLI.

Entry point for all Shell management commands.

Usage:
    makestack start              Start the Shell in production mode
    makestack dev                Start in dev mode (verbose logging, debug API)
    makestack dev --module PATH  Start in dev mode with a local module loaded
    makestack mcp                Run the MCP server over stdio (for Claude Code etc.)
    makestack module create NAME Scaffold a new module
    makestack module validate PATH  Validate a module manifest
    makestack rebuild-frontend   Regenerate module registry and rebuild the frontend
"""

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="makestack")
def app() -> None:
    """Makestack Shell — maker's modular project management toolkit."""


# ---------------------------------------------------------------------------
# makestack start
# ---------------------------------------------------------------------------

@app.command("start")
@click.option("--port", default=3000, show_default=True, help="Port to listen on")
@click.option("--core-url", default="http://localhost:8420", show_default=True,
              help="makestack-core URL")
@click.option("--userdb", default="~/.makestack/userdb.sqlite", show_default=True,
              help="Path to the UserDB SQLite file")
def start(port: int, core_url: str, userdb: str) -> None:
    """Start the Makestack Shell in production mode."""
    import os
    import uvicorn

    os.environ.setdefault("MAKESTACK_PORT", str(port))
    os.environ.setdefault("MAKESTACK_CORE_URL", core_url)
    os.environ.setdefault("MAKESTACK_USERDB_PATH", userdb)
    os.environ["MAKESTACK_DEV_MODE"] = "false"

    click.echo(f"Starting Makestack Shell on port {port}…")
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=port,
        log_config=None,
    )


# ---------------------------------------------------------------------------
# makestack dev
# ---------------------------------------------------------------------------

@app.command("dev")
@click.option("--port", default=3000, show_default=True, help="Port to listen on")
@click.option("--core-url", default="http://localhost:8420", show_default=True,
              help="makestack-core URL")
@click.option("--userdb", default="~/.makestack/userdb.sqlite", show_default=True,
              help="Path to the UserDB SQLite file")
@click.option("--module", "module_path", default=None,
              help="Load a local module from this directory path (for module development)")
def dev(port: int, core_url: str, userdb: str, module_path: str | None) -> None:
    """Start the Makestack Shell in development mode.

    Enables verbose logging, the debug API (/api/dev/*), and hot-reload.
    Use --module to load a local module from a directory path without installing it.
    """
    import os
    import uvicorn

    os.environ["MAKESTACK_PORT"] = str(port)
    os.environ["MAKESTACK_CORE_URL"] = core_url
    os.environ["MAKESTACK_USERDB_PATH"] = userdb
    os.environ["MAKESTACK_DEV_MODE"] = "true"

    if module_path:
        _register_dev_module(module_path, userdb)

    click.echo(f"Starting Makestack Shell in dev mode on port {port}…")
    if module_path:
        click.echo(f"  Dev module: {module_path}")

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_config=None,
    )


def _register_dev_module(module_path: str, userdb_path: str) -> None:
    """Insert or update a local module path in installed_modules.

    Runs synchronously before the Shell starts so the module is visible
    to the loader during the lifespan startup sequence.
    """
    import asyncio
    import json
    from pathlib import Path

    module_dir = Path(module_path).resolve()
    manifest_path = module_dir / "manifest.json"

    if not manifest_path.exists():
        click.echo(f"Error: manifest.json not found at {manifest_path}", err=True)
        raise SystemExit(1)

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        click.echo(f"Error: manifest.json is not valid JSON — {exc}", err=True)
        raise SystemExit(1)

    name = raw.get("name", "")
    version = raw.get("version", "0.0.0")
    if not name:
        click.echo("Error: manifest.json missing 'name' field", err=True)
        raise SystemExit(1)

    async def _insert() -> None:
        from backend.app.userdb import UserDB
        db = UserDB(path=userdb_path, dev_mode=True)
        await db.open()
        await db.run_migrations()

        existing = await db.fetch_one(
            "SELECT name FROM installed_modules WHERE name = ?", [name]
        )
        if existing:
            await db.execute(
                "UPDATE installed_modules SET version = ?, enabled = 1, package_path = ? WHERE name = ?",
                [version, str(module_dir), name],
            )
            click.echo(f"Updated dev module '{name}' → {module_dir}")
        else:
            await db.execute(
                "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
                "VALUES (?, ?, datetime('now'), 1, ?)",
                [name, version, str(module_dir)],
            )
            click.echo(f"Registered dev module '{name}' → {module_dir}")

        await db.close()

    asyncio.run(_insert())


# ---------------------------------------------------------------------------
# makestack module (subcommand group)
# ---------------------------------------------------------------------------

@app.group("module")
def module_group() -> None:
    """Module management commands."""


@module_group.command("create")
@click.argument("name")
@click.option("--output", "-o", default=".", show_default=True,
              help="Parent directory in which to create the module folder")
def module_create(name: str, output: str) -> None:
    """Scaffold a new module skeleton.

    NAME: the module's registered name (lowercase, hyphens only, e.g. my-module).

    Creates a complete module directory with manifest.json, an example backend
    route, an initial migration, an example keyword renderer, and tests.
    The scaffolded module passes 'makestack module validate' immediately.
    """
    import re
    from pathlib import Path

    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        click.echo(
            f"Error: '{name}' is not a valid module name. "
            "Use lowercase letters, digits, and hyphens only (e.g. my-module).",
            err=True,
        )
        raise SystemExit(1)

    snake = name.replace("-", "_")
    upper = snake.upper()
    display_name = name.replace("-", " ").title()
    module_dir = Path(output) / name

    if module_dir.exists():
        click.echo(f"Error: {module_dir} already exists.", err=True)
        raise SystemExit(1)

    # Create directory structure.
    (module_dir / "backend" / "migrations").mkdir(parents=True)
    (module_dir / "frontend" / "components").mkdir(parents=True)
    (module_dir / "tests").mkdir(parents=True)

    subs = dict(name=name, snake=snake, upper=upper, display_name=display_name)

    _write(module_dir / "manifest.json", _render(_MANIFEST_TMPL, subs))
    _write(module_dir / "makestack-package.json", _render(_PACKAGE_TMPL, subs))
    _write(module_dir / "backend" / "__init__.py", "")
    _write(module_dir / "backend" / "routes.py", _render(_ROUTES_TMPL, subs))
    _write(module_dir / "backend" / "migrations" / "__init__.py", "")
    _write(module_dir / "backend" / "migrations" / "001_create_tables.py", _render(_MIGRATION_TMPL, subs))
    _write(module_dir / "frontend" / "components" / "ExampleWidget.tsx", _render(_WIDGET_TMPL, subs))
    _write(module_dir / "frontend" / "keywords.ts", _render(_KEYWORDS_TMPL, subs))
    _write(module_dir / "tests" / "__init__.py", "")
    _write(module_dir / "tests" / "test_routes.py", _render(_TEST_TMPL, subs))

    click.echo(f"\nScaffolded module '{name}' at {module_dir}/\n")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {module_dir}/manifest.json — fill in description and author")
    click.echo(f"  2. Edit {module_dir}/backend/routes.py — add your endpoints")
    click.echo(f"  3. makestack module validate {module_dir}")
    click.echo(f"  4. makestack dev --module {module_dir}")


def _write(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _render(template: str, subs: dict) -> str:
    """Substitute <<KEY>> placeholders — avoids conflicts with curly braces in JSON/TS."""
    result = template
    for k, v in subs.items():
        result = result.replace(f"<<{k}>>", v)
    return result


@module_group.command("validate")
@click.argument("path")
def module_validate(path: str) -> None:
    """Validate a module's manifest.json without starting the Shell.

    PATH: path to the module directory (must contain manifest.json).
    """
    import json
    from pathlib import Path
    from pydantic import ValidationError
    from backend.app.module_manifest import ModuleManifest

    module_dir = Path(path).resolve()
    manifest_path = module_dir / "manifest.json"

    if not manifest_path.exists():
        click.echo(f"Error: manifest.json not found at {manifest_path}", err=True)
        raise SystemExit(1)

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        click.echo(f"Error: manifest.json is not valid JSON — {exc}", err=True)
        raise SystemExit(1)

    try:
        manifest = ModuleManifest.model_validate(raw)
    except ValidationError as exc:
        click.echo(f"Validation failed for '{manifest_path}':", err=True)
        for error in exc.errors():
            loc = " → ".join(str(l) for l in error["loc"])
            click.echo(f"  [{loc}] {error['msg']}", err=True)
        raise SystemExit(1)

    # Additional filesystem checks beyond the Pydantic schema.
    warnings = []
    if not manifest.author:
        warnings.append("'author' field is empty")
    if manifest.has_backend and not (module_dir / "backend" / "routes.py").exists():
        warnings.append("has_backend=true but backend/routes.py not found")
    if manifest.has_frontend and not (module_dir / "frontend").exists():
        warnings.append("has_frontend=true but frontend/ directory not found")
    if manifest.userdb_tables and not (module_dir / "backend" / "migrations").exists():
        warnings.append("userdb_tables declared but backend/migrations/ directory not found")

    click.echo(f"OK  {manifest.name} v{manifest.version} — manifest is valid")
    click.echo(f"    Display name : {manifest.display_name}")
    click.echo(f"    Has backend  : {manifest.has_backend}")
    click.echo(f"    Has frontend : {manifest.has_frontend}")
    click.echo(f"    Keywords     : {len(manifest.keywords)}")
    click.echo(f"    Endpoints    : {len(manifest.api_endpoints)}")
    click.echo(f"    Tables       : {len(manifest.userdb_tables)}")
    click.echo(f"    Panels       : {len(manifest.panels)}")

    if warnings:
        click.echo("\nWarnings:")
        for w in warnings:
            click.echo(f"  !  {w}")
    else:
        click.echo("\nAll checks passed.")


# ---------------------------------------------------------------------------
# makestack mcp
# ---------------------------------------------------------------------------

@app.command("mcp")
def mcp() -> None:
    """Run the MCP server over stdio (for Claude Code and other local AI tools).

    Configure via MAKESTACK_SHELL_URL (default: http://localhost:3000).
    The Shell must already be running.
    """
    from cli.commands.mcp import run
    run()


# ---------------------------------------------------------------------------
# makestack rebuild-frontend
# ---------------------------------------------------------------------------

@app.command("rebuild-frontend")
def rebuild_frontend() -> None:
    """Rebuild the frontend after installing modules or widget packs."""
    import subprocess
    from pathlib import Path

    frontend_dir = Path(__file__).parent.parent / "frontend"
    if not frontend_dir.exists():
        click.echo("Error: frontend/ directory not found.", err=True)
        raise SystemExit(1)

    click.echo("Building frontend…")
    result = subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir))
    if result.returncode != 0:
        click.echo("Build failed.", err=True)
        raise SystemExit(result.returncode)
    click.echo("Frontend rebuilt successfully.")


# ---------------------------------------------------------------------------
# Scaffold templates  (use <<KEY>> placeholders, not {}, to avoid JSON conflicts)
# ---------------------------------------------------------------------------

_MANIFEST_TMPL = """\
{
  "name": "<<name>>",
  "display_name": "<<display_name>>",
  "version": "0.1.0",
  "description": "A Makestack module.",
  "author": "",
  "license": "proprietary",
  "shell_compatibility": ">=0.1.0",
  "has_backend": true,
  "has_frontend": true,
  "keywords": [
    {
      "keyword": "<<upper>>_",
      "description": "Example keyword renderer for <<display_name>>",
      "renderer": "ExampleWidget"
    }
  ],
  "api_endpoints": [
    {
      "method": "GET",
      "path": "/items",
      "description": "List all <<name>> items",
      "parameters": {
        "type": "object",
        "properties": {
          "limit":  {"type": "integer", "description": "Max results"},
          "offset": {"type": "integer", "description": "Pagination offset"}
        }
      }
    }
  ],
  "panels": [],
  "userdb_tables": [
    {
      "name": "<<snake>>_items",
      "description": "Items managed by the <<display_name>> module"
    }
  ],
  "dependencies": {"python": [], "node": []},
  "peer_modules": {"optional": [], "required": []},
  "core_api_permissions": [],
  "config_defaults": {}
}
"""

_PACKAGE_TMPL = """\
{
  "name": "<<name>>",
  "type": "module",
  "version": "0.1.0"
}
"""

_ROUTES_TMPL = '''\
"""Backend routes for the <<display_name>> module.

Mounted at /modules/<<name>>/ by the Shell module loader.
"""

from fastapi import APIRouter, Depends

from makestack_sdk import (
    ModuleUserDB,
    ShellContext,
    get_module_userdb_factory,
    get_shell_context,
    get_logger,
)

log = get_logger("<<name>>")
router = APIRouter()

get_db = get_module_userdb_factory("<<name>>", ["<<snake>>_items"])


@router.get("/items")
async def list_items(
    limit: int = 50,
    offset: int = 0,
    db: ModuleUserDB = Depends(get_db),
    ctx: ShellContext = Depends(get_shell_context),
) -> dict:
    """List all items managed by this module."""
    log.info("list_items", user=ctx.user_id)
    rows = await db.fetch_all(
        "SELECT * FROM <<snake>>_items LIMIT ? OFFSET ?",
        [limit, offset],
    )
    total = await db.count("<<snake>>_items")
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
'''

_MIGRATION_TMPL = '''\
"""Initial tables for the <<name>> module."""

ID = "001_create_<<snake>>_tables"


async def up(conn) -> None:
    """Create <<snake>> module tables."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS <<snake>>_items (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime(\'now\')),
            updated_at TEXT NOT NULL DEFAULT (datetime(\'now\'))
        )
        """
    )
    await conn.commit()
'''

_WIDGET_TMPL = """\
/**
 * Example keyword renderer for the <<display_name>> module.
 * Registered for keyword: <<upper>>_
 */
import type { KeywordContext } from '@/modules/keyword-resolver'

interface Props {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function ExampleWidget({ keyword, value, context }: Props) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent/10 text-accent text-xs font-mono">
      <<upper>>_: {String(value)}
    </span>
  )
}
"""

_KEYWORDS_TMPL = """\
/**
 * Keyword registrations for the <<name>> module.
 */
import { registerKeyword } from '@/modules/keyword-resolver'
import { ExampleWidget } from './components/ExampleWidget'

export function registerModuleKeywords() {
  registerKeyword('<<upper>>_', ExampleWidget, 'module')
}
"""

_TEST_TMPL = '''\
"""Tests for the <<name>> module backend routes."""

import pytest
import pytest_asyncio
from makestack_sdk.testing import MockUserDB, create_test_app

from backend.routes import router


@pytest_asyncio.fixture
async def db():
    database = MockUserDB()
    await database.setup([
        """CREATE TABLE <<snake>>_items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime(\'now\')),
            updated_at TEXT NOT NULL DEFAULT (datetime(\'now\'))
        )"""
    ])
    yield database
    await database.teardown()


@pytest.fixture
def client(db):
    return create_test_app(router, userdb=db)


@pytest.mark.asyncio
async def test_list_items_empty(client):
    response = await client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
'''


if __name__ == "__main__":
    app()
