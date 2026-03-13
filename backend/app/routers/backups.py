"""Backup routes — create, list, and restore UserDB backups.

Backups live in ~/.makestack/backups/ alongside the database.

Endpoints:
    GET  /api/backups          List available backups with timestamps and sizes
    POST /api/backups          Trigger a manual backup, returns the new backup info
    POST /api/backups/restore  Restore from a backup file (body: {backup_path})
"""

from datetime import datetime, timezone
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_userdb
from ..userdb import UserDB

log = structlog.get_logger().bind(component="backups_router")

router = APIRouter(prefix="/api/backups", tags=["backups"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backups_dir(db: UserDB) -> Path:
    """Return the backups directory for this UserDB instance."""
    if db.path == ":memory:":
        return Path.home() / ".makestack" / "backups"
    return Path(db.path).parent / "backups"


def _backup_kind(filename: str) -> str:
    """Classify a backup filename into 'preinstall' or 'manual'."""
    if filename.startswith("userdb-preinstall-"):
        return "preinstall"
    return "manual"


def _file_to_info(f: Path) -> dict:
    stat = f.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return {
        "filename": f.name,
        "path": str(f),
        "size_bytes": stat.st_size,
        "created_at": mtime.isoformat(),
        "kind": _backup_kind(f.name),
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class BackupInfo(BaseModel):
    filename: str
    path: str
    size_bytes: int
    created_at: str
    kind: str  # "manual" | "preinstall"


class RestoreRequest(BaseModel):
    backup_path: str


# ---------------------------------------------------------------------------
# Endpoints — /restore must be declared before the root POST to avoid any
# path-match ambiguity.
# ---------------------------------------------------------------------------


@router.post("/restore", response_model=dict)
async def restore_backup(
    body: RestoreRequest,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Restore the UserDB from a backup file.

    The Shell's active database connection is closed, the backup file is
    copied over the live database, and the connection is reopened. All
    in-flight requests will see the restored state immediately.

    Returns a confirmation with the restored backup path.
    """
    backup_path = Path(body.backup_path)
    if not backup_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Backup file not found",
                "backup_path": body.backup_path,
                "suggestion": "Use GET /api/backups to list available backups.",
            },
        )

    try:
        await db.restore(str(backup_path))
    except Exception as exc:
        log.error("restore_failed", path=str(backup_path), error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Restore failed",
                "detail": str(exc),
                "suggestion": "Check that the backup file is a valid SQLite database.",
            },
        ) from exc

    log.info("userdb_restore_complete", path=str(backup_path))
    return {
        "ok": True,
        "restored_from": str(backup_path),
        "message": "Database restored successfully. The Shell is now using the restored data.",
    }


@router.get("", response_model=list[BackupInfo])
async def list_backups(db: UserDB = Depends(get_userdb)) -> list[BackupInfo]:
    """List all available backups in the backups directory.

    Returns files ordered by creation time, newest first.
    """
    backups_dir = _backups_dir(db)
    if not backups_dir.exists():
        return []

    files = sorted(
        backups_dir.glob("userdb-*.sqlite"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [BackupInfo(**_file_to_info(f)) for f in files]


@router.post("", response_model=BackupInfo, status_code=201)
async def create_backup(db: UserDB = Depends(get_userdb)) -> BackupInfo:
    """Trigger a manual UserDB backup.

    Creates a timestamped backup file in ~/.makestack/backups/ and returns
    the new backup's metadata.
    """
    backups_dir = _backups_dir(db)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"userdb-backup-{ts}.sqlite"

    try:
        await db.backup(str(dest))
    except Exception as exc:
        log.error("backup_failed", dest=str(dest), error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Backup failed",
                "detail": str(exc),
                "suggestion": "Check available disk space and directory permissions.",
            },
        ) from exc

    log.info("manual_backup_created", path=str(dest))
    return BackupInfo(**_file_to_info(dest))
