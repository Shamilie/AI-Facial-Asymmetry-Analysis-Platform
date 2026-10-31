from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, lifespan
from app.core.database import engine

USERS = [
    ("admin@faplatform.org", "Research@2026", "System Administrator", True),
    ("pi@faplatform.org", "Research@2026", "Principal Investigator", False),
    ("coordinator@faplatform.org", "Research@2026", "Research Coordinator", False),
    ("examiner@faplatform.org", "Research@2026", "Clinician / Examiner", False),
    ("analyst@faplatform.org", "Research@2026", "Research Analyst", False),
    ("readonly@faplatform.org", "Research@2026", "Read-only Researcher", False),
]

@pytest.mark.asyncio
async def test_all_six_roles_authentication_and_permissions():
    await engine.dispose()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
            tokens = {}
            for email, password, expected_role, expected_superuser in USERS:
                res = await client.post("/auth/login", json={"email": email, "password": password})
                assert res.status_code == 200, f"Login failed for {email}: {res.text}"
                data = res.json()["data"]
                token = data["access_token"]
                tokens[expected_role] = token
                user = data["user"]

                assert user["email"] == email
                assert user["primary_role"] == expected_role
                assert expected_role in user["roles"]
                assert user["is_superuser"] == expected_superuser
                assert isinstance(user["permissions"], list)
                assert len(user["permissions"]) > 0

                # Verify /auth/me returns same profile
                me_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
                assert me_res.status_code == 200
                me_user = me_res.json()["data"]
                assert me_user["primary_role"] == expected_role

            # 1. Read-only researcher cannot create patient (requires patient:write)
            readonly_token = tokens["Read-only Researcher"]
            res = await client.post(
                "/patients",
                json={
                    "age_at_enrollment": 35,
                    "sex": "M",
                    "fracture_side": "Right",
                    "fracture_type": "Parasymphysis",
                    "study_status": "Enrolled",
                },
                headers={"Authorization": f"Bearer {readonly_token}"},
            )
            assert res.status_code == 403, f"Expected 403 Forbidden for Read-only Researcher, got {res.status_code}"

            # 2. Research Analyst cannot access user management (requires user:manage)
            analyst_token = tokens["Research Analyst"]
            res = await client.get("/admin/users", headers={"Authorization": f"Bearer {analyst_token}"})
            assert res.status_code == 403, f"Expected 403 for analyst accessing /admin/users, got {res.status_code}"

            # 3. Coordinator cannot access user management (requires user:manage)
            coord_token = tokens["Research Coordinator"]
            res = await client.get("/admin/users", headers={"Authorization": f"Bearer {coord_token}"})
            assert res.status_code == 403, f"Expected 403 for coordinator accessing /admin/users, got {res.status_code}"

            # 4. Clinician cannot access audit logs (requires audit:read)
            examiner_token = tokens["Clinician / Examiner"]
            res = await client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {examiner_token}"})
            assert res.status_code == 403, f"Expected 403 for clinician accessing /admin/audit-logs, got {res.status_code}"

            # 5. PI CAN access audit logs (has audit:read)
            pi_token = tokens["Principal Investigator"]
            res = await client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {pi_token}"})
            assert res.status_code == 200, f"Expected 200 for PI accessing /admin/audit-logs, got {res.status_code}"

            # 6. PI CANNOT access user management (requires user:manage)
            res = await client.get("/admin/users", headers={"Authorization": f"Bearer {pi_token}"})
            assert res.status_code == 403, f"Expected 403 for PI accessing /admin/users, got {res.status_code}"

            # 7. System Administrator has full access to user management and update user roles
            admin_token = tokens["System Administrator"]
            res = await client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
            assert res.status_code == 200, f"Expected 200 for admin accessing /admin/users, got {res.text}"
            users_list = res.json()["data"]["users"]
            assert len(users_list) >= 6

            # Find readonly user
            ro_user = next(u for u in users_list if u["email"] == "readonly@faplatform.org")

            # Test PUT /admin/users/{user_id} updating role and details
            update_res = await client.put(
                f"/admin/users/{ro_user['id']}",
                json={
                    "first_name": "Daniel",
                    "last_name": "Brooks",
                    "role_names": ["Read-only Researcher"],
                    "is_active": True,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert update_res.status_code == 200, f"Failed updating user: {update_res.text}"
