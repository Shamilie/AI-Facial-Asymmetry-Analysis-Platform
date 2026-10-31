"""
End-to-end API workflow tests covering authentication, RBAC, patient registration,
visit schedule creation, image upload & quality check, AI analysis, landmark review
preserving original AI predictions, calibration, measurement calculation & approval,
report generation & export, and audit logging.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, lifespan
from app.core.database import engine


@pytest.mark.asyncio
async def test_end_to_end_clinical_research_workflow():
    await engine.dispose()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Log in as Research Coordinator
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": "coordinator@faplatform.org", "password": "Research@2026"},
            )
            assert r.status_code == 200
            coord_token = r.json()["data"]["access_token"]
            coord_headers = {"Authorization": f"Bearer {coord_token}"}

            # 2. Create a new coded patient record with fracture & surgery info -> auto-generates 5 visits
            import uuid

            unique_code = f"SYNTH-TEST-{uuid.uuid4().hex[:6].upper()}"
            r = await client.post(
                "/api/v1/patients",
                headers=coord_headers,
                json={
                    "patient_code": unique_code,
                    "age_at_enrollment": 30,
                    "sex": "Male",
                    "enrollment_date": "2026-10-01",
                    "is_synthetic": True,
                    "consent": {
                        "consent_status": "Obtained",
                        "consent_date": "2026-10-01",
                        "consent_document_ref": "IRB-CONSENT-901",
                    },
                    "fracture": {
                        "fracture_side": "Left",
                        "fracture_classification": "AO/OTA 91-B1 Unilateral Angle Fracture",
                        "fracture_location": "Left mandibular angle",
                        "injury_date": "2026-09-29",
                    },
                    "surgery": {
                        "surgery_date": "2026-10-02",
                        "fixation_type": "ORIF 2.0mm miniplate",
                        "surgical_approach": "Intraoral vestibular",
                        "surgeon_name": "Dr. Marcus Thorne",
                    },
                },
            )
            assert r.status_code == 200, r.text
            pdata = r.json()["data"]
            assert len(pdata["visits"]) == 5
            preop_visit_id = pdata["visits"][0]["id"]

            # 3. Generate synthetic 4-view images + calibrations for the pre-op visit
            r = await client.post(
                f"/api/v1/visits/{preop_visit_id}/images/generate-synthetic",
                headers=coord_headers,
            )
            assert r.status_code == 200
            imgs = r.json()["data"]
            assert len(imgs) == 4

            # 4. Run 11-stage AI analysis and wait briefly for background inline execution
            r = await client.post(
                f"/api/v1/visits/{preop_visit_id}/analysis",
                headers=coord_headers,
            )
            assert r.status_code == 200
            assert len(r.json()["data"]["stages"]) == 11

            import asyncio

            for _ in range(25):
                await asyncio.sleep(0.2)
                r_chk = await client.get(
                    f"/api/v1/analysis/{preop_visit_id}/landmarks",
                    headers=coord_headers,
                )
                if r_chk.status_code == 200:
                    chk_views = r_chk.json()["data"]["views"]
                    f_v = next((v for v in chk_views if v["image_type"] == "Frontal"), None)
                    if f_v and any(lm["code"] == "GO_L" for lm in f_v["landmarks"]):
                        break

            # 5. Inspect landmarks and manually correct a landmark while preserving original AI coords
            r = await client.get(
                f"/api/v1/analysis/{preop_visit_id}/landmarks",
                headers=coord_headers,
            )
            assert r.status_code == 200
            views = r.json()["data"]["views"]
            frontal_view = next(v for v in views if v["image_type"] == "Frontal")
            go_l = next(lm for lm in frontal_view["landmarks"] if lm["code"] == "GO_L")
            orig_x, orig_y = go_l["predicted_x"], go_l["predicted_y"]

            r = await client.patch(
                f"/api/v1/landmarks/{go_l['id']}/review",
                headers=coord_headers,
                json={
                    "corrected_x": orig_x - 3.5,
                    "corrected_y": orig_y + 1.5,
                    "review_status": "Corrected",
                    "approve": True,
                    "correction_reason": "Adjusted to palpated gonial angle",
                },
            )
            assert r.status_code == 200
            updated_lm = r.json()["data"]
            assert updated_lm["predicted_x"] == pytest.approx(orig_x)
            assert updated_lm["examiner_x"] == pytest.approx(orig_x - 3.5)
            assert updated_lm["effective_x"] == pytest.approx(orig_x - 3.5)

            # 6. Recalculate measurements from reviewed landmarks
            r = await client.post(
                "/api/v1/measurements/calculate",
                headers=coord_headers,
                json={"visit_id": preop_visit_id},
            )
            assert r.status_code == 200

            # 7. Verify RBAC: Coordinator cannot approve measurements (requires Examiner/PI/Admin)
            ms = r.json()["data"]["measurements"]
            first_m = next(m for m in ms if m["right_value"] is not None)
            r_forbidden = await client.post(
                f"/api/v1/measurements/{first_m['id']}/approve",
                headers=coord_headers,
                json={"approval_status": "Approved", "comments": "Attempt by coordinator"},
            )
            assert r_forbidden.status_code == 403

            # 8. Log in as Examiner and approve measurements
            r_exam = await client.post(
                "/api/v1/auth/login",
                json={"email": "examiner@faplatform.org", "password": "Research@2026"},
            )
            exam_headers = {"Authorization": f"Bearer {r_exam.json()['data']['access_token']}"}
            r_app = await client.post(
                f"/api/v1/visits/{preop_visit_id}/measurements/approve-all",
                headers=exam_headers,
                json={"approval_status": "Approved", "comments": "Examiner sign-off"},
            )
            assert r_app.status_code == 200
            assert r_app.json()["data"]["summary"]["approved"] > 0

            # 9. Generate and download a PDF patient research report
            r_rep = await client.post(
                "/api/v1/reports/generate",
                headers=exam_headers,
                json={"patient_id": pdata["id"], "visit_id": preop_visit_id},
            )
            assert r_rep.status_code == 200
            report_id = r_rep.json()["data"]["id"]

            r_pdf = await client.get(
                f"/api/v1/reports/{report_id}/download?format=PDF",
                headers=exam_headers,
            )
            assert r_pdf.status_code == 200
            assert r_pdf.content.startswith(b"%PDF")

            # 10. Test multipart file upload of a non-synthetic JPEG image to /visits/{id}/images
            import io
            from PIL import Image, ImageDraw

            im = Image.new("RGB", (600, 600), (210, 210, 215))
            draw = ImageDraw.Draw(im)
            draw.ellipse((180, 120, 420, 480), fill=(235, 200, 178), outline=(90, 70, 60), width=3)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=92)
            jpeg_bytes = buf.getvalue()

            r_up = await client.post(
                f"/api/v1/visits/{preop_visit_id}/images",
                headers=coord_headers,
                data={"image_type": "Frontal", "replace_existing": "true"},
                files={"file": ("patient_frontal.jpg", jpeg_bytes, "image/jpeg")},
            )
            assert r_up.status_code == 200, r_up.text
            assert r_up.json()["data"]["image_type"] == "Frontal"
            assert r_up.json()["data"]["quality_result"] is not None

            # 11. Verify Database-Backed Binary Storage (stored_blobs table) and Follow-Up Comparison endpoint
            r_db = await client.get("/api/v1/system/database-status")
            assert r_db.status_code == 200
            db_info = r_db.json()["data"]
            assert db_info["storage_backend"] == "database"
            assert db_info["blob_storage"]["total_blobs"] > 0
            assert db_info["blob_storage"]["by_category"]["originals"]["count"] > 0

            r_fu = await client.get(
                f"/api/v1/measurements/patients/{pdata['id']}/follow-up",
                headers=exam_headers,
            )
            assert r_fu.status_code == 200, r_fu.text
            assert len(r_fu.json()["data"]["visits"]) == 5

            # Also verify Follow-Up Comparison for a seeded patient with ClinicalAssessment records
            r_list = await client.get("/api/v1/patients?page=1&page_size=10", headers=exam_headers)
            assert r_list.status_code == 200
            seeded_id = r_list.json()["data"][0]["id"]
            r_fu_seeded = await client.get(
                f"/api/v1/measurements/patients/{seeded_id}/follow-up",
                headers=exam_headers,
            )
            assert r_fu_seeded.status_code == 200, r_fu_seeded.text
            assert len(r_fu_seeded.json()["data"]["visits"]) == 5

            # 12. Verify full 11-stage AI pipeline on a fresh visit with a single uploaded JPEG image:
            #     Must use real AI models (is_demo=False), auto-calibrate all views, and generate all 14 measurements!
            postop_visit_id = pdata["visits"][1]["id"]
            r_up2 = await client.post(
                f"/api/v1/visits/{postop_visit_id}/images",
                headers=coord_headers,
                data={"image_type": "Frontal", "replace_existing": "true"},
                files={"file": ("postop_frontal.jpg", jpeg_bytes, "image/jpeg")},
            )
            assert r_up2.status_code == 200

            r_run2 = await client.post(
                f"/api/v1/ai/visits/{postop_visit_id}/run",
                headers=coord_headers,
            )
            assert r_run2.status_code == 200
            for stage in r_run2.json()["data"]["stages"]:
                assert stage["is_demo"] is False, f"Stage {stage['task_type']} should not be Demo"
                assert stage["provider"] != "Demo"

            for _ in range(40):
                await asyncio.sleep(0.25)
                r_pipe = await client.get(
                    f"/api/v1/ai/visits/{postop_visit_id}/pipeline",
                    headers=coord_headers,
                )
                if r_pipe.status_code == 200 and r_pipe.json()["data"]["overall_status"] == "Completed":
                    break

            r_ms2 = await client.get(
                f"/api/v1/measurements/visits/{postop_visit_id}",
                headers=coord_headers,
            )
            assert r_ms2.status_code == 200
            ms2_data = r_ms2.json()["data"]
            assert ms2_data["summary"]["total"] == 14
            assert ms2_data["summary"]["unscaled"] == 0
            assert ms2_data["summary"]["missing"] == 0
            for m_item in ms2_data["measurements"]:
                assert m_item["right_value"] is not None, f"Missing right_value for {m_item['code']}"
                assert m_item["left_value"] is not None, f"Missing left_value for {m_item['code']}"
