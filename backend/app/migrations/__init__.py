"""
Shell core migrations.

Each migration module in this package must define:
  - ID: str — unique identifier (e.g. "001_initial_schema")
  - async def up(conn) — apply the migration to the given aiosqlite connection
"""
