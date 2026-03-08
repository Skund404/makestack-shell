"""Tests for /api/users/* — user profile and stats endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# GET /api/users/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_profile_returns_default_user(client: AsyncClient) -> None:
    resp = await client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "default"
    assert data["name"] == "Maker"   # seed value from migration 001
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_profile_has_new_fields(client: AsyncClient) -> None:
    """Migration 004 columns should be present with defaults."""
    resp = await client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["bio"] == ""
    assert data["timezone"] == "UTC"
    assert data["locale"] == "en"
    assert data.get("avatar_path") is None


# ---------------------------------------------------------------------------
# PUT /api/users/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_name(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"name": "Alice"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice"


@pytest.mark.asyncio
async def test_update_name_reflected_in_get(client: AsyncClient) -> None:
    await client.put("/api/users/me", json={"name": "Bob"})
    resp = await client.get("/api/users/me")
    assert resp.json()["name"] == "Bob"


@pytest.mark.asyncio
async def test_update_bio(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"bio": "I make leather bags."})
    assert resp.status_code == 200
    assert resp.json()["bio"] == "I make leather bags."


@pytest.mark.asyncio
async def test_update_timezone(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"timezone": "America/New_York"})
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_update_locale(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"locale": "de"})
    assert resp.status_code == 200
    assert resp.json()["locale"] == "de"


@pytest.mark.asyncio
async def test_update_avatar_path(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"avatar_path": "/img/avatar.png"})
    assert resp.status_code == 200
    assert resp.json()["avatar_path"] == "/img/avatar.png"


@pytest.mark.asyncio
async def test_clear_avatar_path(client: AsyncClient) -> None:
    """Empty string should clear (set to null) the avatar path."""
    await client.put("/api/users/me", json={"avatar_path": "/img/avatar.png"})
    resp = await client.put("/api/users/me", json={"avatar_path": ""})
    assert resp.status_code == 200
    assert resp.json()["avatar_path"] is None


@pytest.mark.asyncio
async def test_update_multiple_fields_at_once(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={
        "name": "Crafty Maker",
        "bio": "Wood and leather.",
        "timezone": "Europe/Berlin",
        "locale": "de",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Crafty Maker"
    assert data["bio"] == "Wood and leather."
    assert data["timezone"] == "Europe/Berlin"
    assert data["locale"] == "de"


@pytest.mark.asyncio
async def test_update_empty_body_is_no_op(client: AsyncClient) -> None:
    """A PUT with no fields should return the current profile unchanged."""
    original = (await client.get("/api/users/me")).json()
    resp = await client.put("/api/users/me", json={})
    assert resp.status_code == 200
    assert resp.json()["name"] == original["name"]


@pytest.mark.asyncio
async def test_update_blank_name_rejected(client: AsyncClient) -> None:
    resp = await client.put("/api/users/me", json={"name": "   "})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "name" in str(detail).lower()


@pytest.mark.asyncio
async def test_update_preserves_other_fields(client: AsyncClient) -> None:
    """Patching one field should not clobber unrelated fields."""
    await client.put("/api/users/me", json={"bio": "Maker of things."})
    await client.put("/api/users/me", json={"name": "Alice"})
    resp = await client.get("/api/users/me")
    assert resp.json()["bio"] == "Maker of things."
    assert resp.json()["name"] == "Alice"


# ---------------------------------------------------------------------------
# GET /api/users/me/stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_empty_db(client: AsyncClient) -> None:
    """Fresh DB — all counts should be zero."""
    resp = await client.get("/api/users/me/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["workshops_count"] == 0
    assert data["inventory_count"] == 0
    assert data["stale_inventory_count"] == 0
    assert data["modules_installed"] == 0
    assert data["modules_enabled"] == 0
    assert data["active_workshop_id"] is None
    assert data["active_workshop_name"] is None


@pytest.mark.asyncio
async def test_stats_reflects_workshops(client: AsyncClient) -> None:
    await client.post("/api/workshops", json={"name": "Leatherwork"})
    await client.post("/api/workshops", json={"name": "Wood"})
    resp = await client.get("/api/users/me/stats")
    assert resp.json()["workshops_count"] == 2


@pytest.mark.asyncio
async def test_stats_active_workshop_name(client: AsyncClient) -> None:
    ws = (await client.post("/api/workshops", json={"name": "CNC Projects"})).json()
    await client.put("/api/workshops/active", json={"workshop_id": ws["id"]})
    resp = await client.get("/api/users/me/stats")
    data = resp.json()
    assert data["active_workshop_id"] == ws["id"]
    assert data["active_workshop_name"] == "CNC Projects"


@pytest.mark.asyncio
async def test_stats_active_workshop_none(client: AsyncClient) -> None:
    """When no active workshop is set stats should return None for both fields."""
    resp = await client.get("/api/users/me/stats")
    assert resp.json()["active_workshop_id"] is None
    assert resp.json()["active_workshop_name"] is None
