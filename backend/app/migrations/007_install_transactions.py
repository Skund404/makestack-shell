"""Migration 007 — create install_transactions table.

Tracks the step-by-step progress of package installs so that a crash during
installation can be detected on next startup and the partial install rolled back.

Startup recovery (Phase 10D) queries for rows with status='in_progress' before
any modules are loaded and completes the rollback automatically.
"""

ID = "007_install_transactions"


async def up(conn) -> None:
    """Create install_transactions table."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS install_transactions (
            id              TEXT PRIMARY KEY,
            package_name    TEXT NOT NULL,
            package_version TEXT,
            package_type    TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'in_progress',
            steps_completed TEXT NOT NULL DEFAULT '[]',
            failed_step     TEXT,
            backup_path     TEXT,
            started_at      TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at     TEXT,
            error           TEXT
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_install_tx_status "
        "ON install_transactions(status)"
    )
    await conn.commit()
