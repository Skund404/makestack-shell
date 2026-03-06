"""Tests for workshop routes — pure UserDB operations, no Core dependency."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# POST /api/workshops — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workshop(client: AsyncClient):
    resp = await client.post("/api/workshops", json={"name": "Leatherwork"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Leatherwork"
    assert body["slug"] == "leatherwork"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_workshop_with_description(client: AsyncClient):
    resp = await client.post(
        "/api/workshops",
        json={"name": "2024 Projects", "description": "All projects from 2024", "icon": "folder", "color": "#ff0000"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] == "All projects from 2024"
    assert body["icon"] == "folder"
    assert body["color"] == "#ff0000"


@pytest.mark.asyncio
async def test_create_workshop_slug_is_url_safe(client: AsyncClient):
    resp = await client.post("/api/workshops", json={"name": "My Amazing Workshop!"})
    assert resp.status_code == 201
    slug = resp.json()["slug"]
    assert slug == "my-amazing-workshop"


@pytest.mark.asyncio
async def test_create_duplicate_name_gets_unique_slug(client: AsyncClient):
    resp1 = await client.post("/api/workshops", json={"name": "Duplicate"})
    resp2 = await client.post("/api/workshops", json={"name": "Duplicate"})
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["slug"] != resp2.json()["slug"]


# ---------------------------------------------------------------------------
# GET /api/workshops — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_workshops_empty(client: AsyncClient):
    resp = await client.get("/api/workshops")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_workshops_returns_created(client: AsyncClient):
    await client.post("/api/workshops", json={"name": "Workshop A"})
    await client.post("/api/workshops", json={"name": "Workshop B"})
    resp = await client.get("/api/workshops")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_list_workshops_pagination(client: AsyncClient):
    for i in range(5):
        await client.post("/api/workshops", json={"name": f"WS {i}"})
    resp = await client.get("/api/workshops?limit=2&offset=0")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# GET /api/workshops/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_workshop_with_members(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Detail WS"})
    ws_id = create_resp.json()["id"]

    resp = await client.get(f"/api/workshops/{ws_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == ws_id
    assert "members" in body
    assert isinstance(body["members"], list)


@pytest.mark.asyncio
async def test_get_workshop_404(client: AsyncClient):
    resp = await client.get("/api/workshops/nonexistent-id")
    assert resp.status_code == 404
    assert "suggestion" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PUT /api/workshops/{id} — update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_workshop_name(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Old Name"})
    ws_id = create_resp.json()["id"]

    resp = await client.put(f"/api/workshops/{ws_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_workshop_partial(client: AsyncClient):
    create_resp = await client.post(
        "/api/workshops",
        json={"name": "Partial", "description": "original"},
    )
    ws_id = create_resp.json()["id"]

    resp = await client.put(f"/api/workshops/{ws_id}", json={"icon": "star"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["icon"] == "star"
    assert body["description"] == "original"  # unchanged


@pytest.mark.asyncio
async def test_update_workshop_404(client: AsyncClient):
    resp = await client.put("/api/workshops/nonexistent-id", json={"name": "X"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workshops/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_workshop(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "To Delete"})
    ws_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/workshops/{ws_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/workshops/{ws_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workshop_404(client: AsyncClient):
    resp = await client.delete("/api/workshops/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Members — POST /api/workshops/{id}/members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member_to_workshop(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Member WS"})
    ws_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/workshops/{ws_id}/members",
        json={"primitive_path": "tools/chisel/manifest.json", "primitive_type": "tool"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["primitive_path"] == "tools/chisel/manifest.json"
    assert body["primitive_type"] == "tool"


@pytest.mark.asyncio
async def test_add_member_idempotent(client: AsyncClient):
    """Adding the same primitive twice should not error — returns the existing record."""
    create_resp = await client.post("/api/workshops", json={"name": "Idem WS"})
    ws_id = create_resp.json()["id"]

    payload = {"primitive_path": "tools/chisel/manifest.json", "primitive_type": "tool"}
    resp1 = await client.post(f"/api/workshops/{ws_id}/members", json=payload)
    resp2 = await client.post(f"/api/workshops/{ws_id}/members", json=payload)

    assert resp1.status_code == 201
    assert resp2.status_code == 201


@pytest.mark.asyncio
async def test_add_member_includes_in_workshop_detail(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Detail Member WS"})
    ws_id = create_resp.json()["id"]
    await client.post(
        f"/api/workshops/{ws_id}/members",
        json={"primitive_path": "tools/chisel/manifest.json", "primitive_type": "tool"},
    )

    detail = await client.get(f"/api/workshops/{ws_id}")
    members = detail.json()["members"]
    assert len(members) == 1
    assert members[0]["primitive_path"] == "tools/chisel/manifest.json"


@pytest.mark.asyncio
async def test_add_member_404_for_unknown_workshop(client: AsyncClient):
    resp = await client.post(
        "/api/workshops/nonexistent-id/members",
        json={"primitive_path": "tools/chisel/manifest.json", "primitive_type": "tool"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Members — DELETE /api/workshops/{id}/members/{path}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Remove WS"})
    ws_id = create_resp.json()["id"]
    await client.post(
        f"/api/workshops/{ws_id}/members",
        json={"primitive_path": "tools/chisel/manifest.json", "primitive_type": "tool"},
    )

    del_resp = await client.delete(f"/api/workshops/{ws_id}/members/tools/chisel/manifest.json")
    assert del_resp.status_code == 204

    detail = await client.get(f"/api/workshops/{ws_id}")
    assert detail.json()["members"] == []


@pytest.mark.asyncio
async def test_remove_member_404(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "No Member WS"})
    ws_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/workshops/{ws_id}/members/tools/nonexistent/manifest.json")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/workshops/active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_active_workshop(client: AsyncClient):
    create_resp = await client.post("/api/workshops", json={"name": "Active WS"})
    ws_id = create_resp.json()["id"]

    resp = await client.put("/api/workshops/active", json={"workshop_id": ws_id})
    assert resp.status_code == 200
    assert resp.json()["active_workshop_id"] == ws_id


@pytest.mark.asyncio
async def test_clear_active_workshop(client: AsyncClient):
    resp = await client.put("/api/workshops/active", json={"workshop_id": None})
    assert resp.status_code == 200
    assert resp.json()["active_workshop_id"] is None


@pytest.mark.asyncio
async def test_set_active_workshop_404_for_unknown(client: AsyncClient):
    resp = await client.put("/api/workshops/active", json={"workshop_id": "nonexistent-id"})
    assert resp.status_code == 404
