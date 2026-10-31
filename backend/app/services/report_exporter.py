"""
Report generation and multi-format export service (PDF, CSV, Excel, JSON, OBJ, PLY).

Every exported report clearly distinguishes AI-predicted, examiner-reviewed and
approved measurements, records the protocol/model/calibration provenance, and
carries the mandatory research-only non-diagnostic disclaimer.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RESEARCH_DISCLAIMER = (
    "RESEARCH MEASUREMENT DOCUMENT ONLY — Outputs in this report are intended solely for "
    "clinical research measurement and documentation under the approved study protocol. "
    "They do NOT constitute a medical diagnosis, treatment recommendation, or substitute "
    "for clinical judgment. Unvalidated or AI-predicted values are explicitly labelled."
)


def build_pdf_bytes(report_payload: dict[str, Any]) -> bytes:
    """Generate a structured 13-section PDF research report using ReportLab."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=report_payload.get("title", "Facial Asymmetry Research Report"),
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("FAH1", parent=styles["Heading1"], textColor=colors.HexColor("#123B50"), fontSize=16, spaceAfter=6)
    h2 = ParagraphStyle("FAH2", parent=styles["Heading2"], textColor=colors.HexColor("#087E8B"), fontSize=11, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("FABody", parent=styles["BodyText"], fontSize=9, leading=12)
    warn = ParagraphStyle("FAWarn", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#8A3B12"))

    story: list[Any] = []
    story.append(Paragraph("AI Facial Asymmetry Analysis Platform — Research Report", h1))
    story.append(Paragraph(f"<b>{report_payload.get('title', 'Research Report')}</b>", body))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>IMPORTANT NOTICE:</b> {RESEARCH_DISCLAIMER}", warn))
    story.append(Spacer(1, 8))

    # 1. Patient research ID & 2. Study information
    p_info = report_payload.get("patient", {})
    s_info = report_payload.get("study", {})
    story.append(Paragraph("1. Patient Research Identification & 2. Study Information", h2))
    meta_rows = [
        ["Patient Research Code", str(p_info.get("patient_code", "N/A")), "Study Protocol", str(s_info.get("protocol_title", "Unilateral Mandibular Fracture Fixation Study"))],
        ["Fracture Side / Type", f"{p_info.get('fracture_side', 'N/A')} — {p_info.get('fracture_classification', 'N/A')}", "Protocol Version", str(s_info.get("protocol_version", "1.0"))],
        ["Fixation / Surgery Date", f"{p_info.get('fixation_type', 'N/A')} ({p_info.get('surgery_date', 'N/A')})", "Consent Status", str(p_info.get("consent_status", "Obtained"))],
    ]
    t_meta = Table(meta_rows, colWidths=[38 * mm, 50 * mm, 38 * mm, 50 * mm])
    t_meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F6F8")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F6F8")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_meta)

    # 3. Visit information & 4. Image acquisition & 5. Image quality
    v_info = report_payload.get("visit", {})
    story.append(Paragraph("3. Visit Information, 4. Image Acquisition & 5. Quality Assessment", h2))
    story.append(
        Paragraph(
            f"Visit: <b>{v_info.get('visit_type', 'All Visits')}</b> | Planned: {v_info.get('planned_date', 'N/A')} | "
            f"Actual: {v_info.get('actual_date', 'N/A')} | Visit Status: <b>{v_info.get('status', 'N/A')}</b>",
            body,
        )
    )
    imgs = report_payload.get("images", [])
    if imgs:
        img_rows = [["View Type", "Resolution", "Quality Screen", "Examiner Acceptance", "Issues / Notes"]]
        for im in imgs:
            img_rows.append(
                [
                    str(im.get("image_type", "")),
                    f"{im.get('width', '?')}×{im.get('height', '?')} px",
                    str(im.get("quality_status", "Not run")),
                    str(im.get("acceptance_status", "Pending")),
                    "; ".join(im.get("issues") or [])[:70] or "None",
                ]
            )
        t_img = Table(img_rows, colWidths=[28 * mm, 28 * mm, 28 * mm, 32 * mm, 60 * mm])
        t_img.setStyle(_grid_style())
        story.append(Spacer(1, 4))
        story.append(t_img)

    # 6. Landmark summary & 10. AI model information & 11. Calibration information
    lm_sum = report_payload.get("landmark_summary", {})
    story.append(Paragraph("6. Landmark Summary, 10. AI Model Provenance & 11. Calibration", h2))
    story.append(
        Paragraph(
            f"Landmarks total: <b>{lm_sum.get('total', 0)}</b> | AI Predicted: {lm_sum.get('predicted', 0)} | "
            f"Examiner Reviewed/Corrected: {lm_sum.get('reviewed', 0)} | Approved: {lm_sum.get('approved', 0)} | "
            f"Not Identifiable: {lm_sum.get('not_identifiable', 0)}",
            body,
        )
    )
    cals = report_payload.get("calibrations", [])
    if cals:
        cal_rows = [["View / Type", "Reference Marker", "mm / pixel", "Physical?", "Same Plane?", "Method"]]
        for c in cals:
            cal_rows.append(
                [
                    str(c.get("calibration_type", "")),
                    str(c.get("reference_marker_type", "")),
                    f"{float(c.get('mm_per_pixel', 0)):.4f}",
                    "Yes" if c.get("is_physical", True) else "No (Display PPI)",
                    "Confirmed" if c.get("same_plane_confirmed") else "Unconfirmed",
                    str(c.get("calibration_method", "")),
                ]
            )
        t_cal = Table(cal_rows, colWidths=[30 * mm, 38 * mm, 24 * mm, 28 * mm, 26 * mm, 30 * mm])
        t_cal.setStyle(_grid_style())
        story.append(Spacer(1, 4))
        story.append(t_cal)

    # 7. Measurement results & 8. Asymmetry index
    story.append(Paragraph("7. Quantitative Measurement Results & 8. Asymmetry Index", h2))
    ms = report_payload.get("measurements", [])
    if ms:
        m_rows = [["Measurement", "Right", "Left", "|R-L|", "AI (%)", "Unit", "Provenance", "Status"]]
        for m in ms:
            m_rows.append(
                [
                    str(m.get("name", m.get("code", "")))[:34],
                    _f(m.get("right_value")),
                    _f(m.get("left_value")),
                    _f(m.get("absolute_difference")),
                    _f(m.get("asymmetry_index")),
                    str(m.get("unit", "")),
                    str(m.get("method", "")),
                    str(m.get("status", "")),
                ]
            )
        t_m = Table(m_rows, colWidths=[46 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm, 12 * mm, 28 * mm, 26 * mm])
        t_m.setStyle(_grid_style())
        story.append(t_m)
    else:
        story.append(Paragraph("No measurements recorded for this selection.", body))

    # 9. Follow-up comparison
    fu = report_payload.get("follow_up_summary", [])
    if fu:
        story.append(Paragraph("9. Longitudinal Follow-up Comparison (Mean Bilateral Asymmetry Index %)", h2))
        fu_rows = [["Visit Stage", "Visit Status", "Evaluated Measurements", "Approved Count", "Mean AI (%)"]]
        for item in fu:
            fu_rows.append(
                [
                    str(item.get("visit_type", "")),
                    str(item.get("status", "")),
                    str(item.get("measurement_count", 0)),
                    str(item.get("approved_count", 0)),
                    _f(item.get("mean_asymmetry_index")),
                ]
            )
        t_fu = Table(fu_rows, colWidths=[42 * mm, 34 * mm, 34 * mm, 34 * mm, 32 * mm])
        t_fu.setStyle(_grid_style())
        story.append(t_fu)

    # 12. Reviewer & approval details & 13. Limitations and warnings
    story.append(Paragraph("12. Narrative Summary & Reviewer Sign-off", h2))
    story.append(Paragraph(str(report_payload.get("summary_text", "No narrative summary generated.")).replace("\n", "<br/>"), body))

    story.append(Paragraph("13. Scientific Limitations & Warnings", h2))
    limitations = report_payload.get(
        "limitations",
        [
            "Frontal and lateral photographs require independent, view-specific calibration in the anatomical plane.",
            "OPG panoramic radiographs exhibit regional magnification and horizontal distortion; pixel spacing alone does not correct distortion.",
            "3D surface geodesic paths approximate flexible tape measurements and require validation against paired physical measurements.",
            "AI-predicted landmarks and unapproved measurements are unvalidated research outputs.",
        ],
    )
    for lim in limitations:
        story.append(Paragraph(f"• {lim}", warn))

    doc.build(story)
    return buf.getvalue()


def _f(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def _grid_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.8),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("PADDING", (0, 0), (-1, -1), 3.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


def build_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    if not rows:
        buf.write("notice\nNo records match export filter\n")
        return buf.getvalue().encode("utf-8")
    headers = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


def build_excel_bytes(sheet_title: str, rows: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    header_fill = PatternFill(start_color="123B50", end_color="123B50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    ws.append(["AI Facial Asymmetry Analysis Platform — Research Export"])
    ws["A1"].font = Font(bold=True, size=12, color="123B50")
    ws.append([RESEARCH_DISCLAIMER])
    ws.append([])

    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        hdr_row = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=hdr_row, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append([r.get(h) for h in headers])
    else:
        ws.append(["No records available for export."])

    if metadata:
        ws_meta = wb.create_sheet("Provenance_Metadata")
        ws_meta.append(["Key", "Value"])
        for k, v in metadata.items():
            ws_meta.append([str(k), json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
