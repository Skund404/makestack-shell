"""SDK surface: Shell runtime context for module authors.

Provides access to the current user ID, active workshop, Shell version, and
dev mode flag. Injected via FastAPI dependency.

Usage in a module's routes.py:

    from makestack_sdk.context import ShellContext, get_shell_context
    from fastapi import APIRouter, Depends

    router = APIRouter()

    @router.get("/my-endpoint")
    async def my_endpoint(ctx: ShellContext = Depends(get_shell_context)):
        user_id = ctx.user_id
        workshop_id = ctx.active_workshop_id
        ...
"""

from dataclasses import dataclass

from fastapi import Request

from backend.app.userdb import UserDB


@dataclass
class ShellContext:
    """Runtime context for a Shell request."""

    user_id: str
    active_workshop_id: str | None
    shell_version: str
    dev_mode: bool


async def get_shell_context(request: Request) -> ShellContext:
    """FastAPI dependency: inject the current Shell runtime context.

    Reads user_id and active_workshop_id from UserDB, and Shell version and
    dev_mode from app.state.
    """
    db: UserDB = request.app.state.userdb
    dev_mode: bool = getattr(request.app.state, "dev_mode", False)
    shell_version: str = getattr(request.app.state, "config", {}).get("shell_version", "0.1.0")

    # Read active workshop from user preferences (key: "active_workshop_id").
    pref_row = await db.fetch_one(
        "SELECT value FROM user_preferences WHERE user_id = 'default' AND key = 'active_workshop_id'"
    )
    active_workshop_id: str | None = None
    if pref_row:
        import json
        try:
            active_workshop_id = json.loads(pref_row["value"])
        except (ValueError, TypeError):
            active_workshop_id = None

    return ShellContext(
        user_id="default",
        active_workshop_id=active_workshop_id,
        shell_version=shell_version,
        dev_mode=dev_mode,
    )


__all__ = ["ShellContext", "get_shell_context"]
