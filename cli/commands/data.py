"""CLI commands for exporting and importing personal UserDB data.

Usage:
    makestack export --output backup.json
    makestack export --only inventory --output inv.json
    makestack import backup.json
    makestack import backup.json --only workshops
    makestack import backup.json --strategy overwrite
"""

import json
import sys
from pathlib import Path

import click


def _shell_url() -> str:
    import os
    return os.getenv("MAKESTACK_SHELL_URL", "http://localhost:3000")


def _api_get(path: str, **params) -> dict:
    """HTTP GET against the Shell API."""
    import httpx
    url = _shell_url() + path
    try:
        resp = httpx.get(url, params=params or None, timeout=60.0)
        return resp.json()
    except httpx.ConnectError:
        click.echo(
            f"Error: Cannot connect to Shell at {_shell_url()}. "
            "Is the Shell running?",
            err=True,
        )
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _api_post(path: str, data: dict, **params) -> dict:
    """HTTP POST against the Shell API."""
    import httpx
    url = _shell_url() + path
    try:
        resp = httpx.post(url, json=data, params=params or None, timeout=120.0)
        return resp.json()
    except httpx.ConnectError:
        click.echo(
            f"Error: Cannot connect to Shell at {_shell_url()}. "
            "Is the Shell running?",
            err=True,
        )
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@click.command("export")
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
@click.option(
    "--only",
    default=None,
    help="Export only this section: workshops, inventory, preferences, or module:<name>",
)
def export_cmd(output: str | None, only: str | None) -> None:
    """Export personal data (inventory, workshops, preferences) to portable JSON.

    The exported JSON can be re-imported with 'makestack import'.
    Catalogue data is not exported — it lives in the Git-based catalogue.
    """
    params = {}
    if only:
        params["only"] = only

    click.echo("Exporting…", err=True)
    result = _api_get("/api/data/export", **params)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        sys.exit(1)

    export_json = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        path = Path(output)
        path.write_text(export_json, encoding="utf-8")
        sections = result.get("sections", {})
        counts = {k: len(v) if isinstance(v, list) else len(v) for k, v in sections.items() if v}
        click.echo(f"Exported to {path}")
        for section, count in counts.items():
            click.echo(f"  {section}: {count} item(s)")
    else:
        click.echo(export_json)


@click.command("import")
@click.argument("file_path")
@click.option(
    "--only",
    default=None,
    help="Import only this section: workshops, inventory, preferences",
)
@click.option(
    "--strategy",
    default="additive",
    type=click.Choice(["additive", "overwrite", "skip_conflicts"]),
    show_default=True,
    help="Conflict resolution strategy",
)
def import_cmd(file_path: str, only: str | None, strategy: str) -> None:
    """Import personal data from a JSON export file.

    FILE_PATH: path to the .json file produced by 'makestack export'.

    Strategies:
      additive (default) — add new items, skip items that already exist
      overwrite          — add new items, replace existing items
      skip_conflicts     — same as additive
    """
    path = Path(file_path)
    if not path.exists():
        click.echo(f"Error: File not found: {path}", err=True)
        sys.exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        click.echo(f"Error: Not valid JSON — {exc}", err=True)
        sys.exit(1)

    params: dict = {"strategy": strategy}
    if only:
        params["only"] = only

    click.echo(f"Importing from {path} (strategy: {strategy})…", err=True)
    result = _api_post("/api/data/import", data={"data": data}, **params)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        if "suggestion" in result:
            click.echo(f"  {result['suggestion']}", err=True)
        sys.exit(1)

    # Show summary
    imported = result.get("imported", {})
    skipped = result.get("skipped", {})
    replaced = result.get("replaced", {})
    errors = result.get("errors", [])

    click.echo("Import complete:")
    all_sections = set(imported) | set(skipped) | set(replaced)
    for section in sorted(all_sections):
        parts = []
        if imported.get(section):
            parts.append(f"{imported[section]} added")
        if replaced.get(section):
            parts.append(f"{replaced[section]} replaced")
        if skipped.get(section):
            parts.append(f"{skipped[section]} skipped")
        click.echo(f"  {section}: {', '.join(parts) or 'nothing'}")

    if errors:
        click.echo(f"\n{len(errors)} error(s):")
        for err in errors[:10]:  # Show first 10
            click.echo(f"  ! {err}", err=True)
        if len(errors) > 10:
            click.echo(f"  ... and {len(errors) - 10} more", err=True)
