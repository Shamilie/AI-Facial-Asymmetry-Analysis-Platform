from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, lifespan
from app.core.database import engine
from app.services.system_settings import get_cached_setting_value

@pytest.mark.asyncio
async def test_database_backed_system_settings():
    await engine.dispose()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
            # 1. Login as System Administrator
            r = await client.post(
                "/auth/login",
                json={"email": "admin@faplatform.org", "password": "Research@2026"},
            )
            assert r.status_code == 200
            admin_token = r.json()["data"]["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            # 2. Login as Read-only Researcher
            r = await client.post(
                "/auth/login",
                json={"email": "readonly@faplatform.org", "password": "Research@2026"},
            )
            assert r.status_code == 200
            readonly_token = r.json()["data"]["access_token"]
            readonly_headers = {"Authorization": f"Bearer {readonly_token}"}

            # 3. List settings as admin
            res = await client.get("/admin/settings", headers=admin_headers)
            assert res.status_code == 200
            data = res.json()["data"]
            assert "settings" in data
            assert "governance" in data
            settings_list = data["settings"]
            assert any(s["key"] == "GEMINI_API_KEY" for s in settings_list)

            # 4. Read-only user cannot update settings (requires config:manage)
            res = await client.put(
                "/admin/settings/GEMINI_API_KEY",
                headers=readonly_headers,
                json={"value": "AIzaSyTestKey123456789"},
            )
            assert res.status_code == 403

            # 5. Admin updates GEMINI_API_KEY in database table
            new_key = "AIzaSyLiveDbConfiguredKey9999"
            res = await client.put(
                "/admin/settings/GEMINI_API_KEY",
                headers=admin_headers,
                json={"value": new_key},
            )
            assert res.status_code == 200
            assert res.json()["data"]["updated"] is True

            # 6. Verify database value is returned masked in settings list
            res = await client.get("/admin/settings", headers=admin_headers)
            gemini_setting = next(s for s in res.json()["data"]["settings"] if s["key"] == "GEMINI_API_KEY")
            assert gemini_setting["is_configured"] is True
            assert gemini_setting["value"] == "AIzaSy...9999"  # Masked!

            # 7. Verify runtime service resolves the new key from database
            resolved_key = get_cached_setting_value("GEMINI_API_KEY")
            assert resolved_key == new_key

            # 8. Verify audit log entry was created for config.update
            audit_res = await client.get("/admin/audit-logs?action_type=config.update", headers=admin_headers)
            assert audit_res.status_code == 200
            audit_items = audit_res.json()["data"]["items"]
            assert len(audit_items) > 0
            latest = audit_items[0]
            assert latest["action_type"] == "config.update"
            assert latest["entity_type"] == "system_setting"
