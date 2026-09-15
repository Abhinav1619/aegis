"""Per-device PDF compliance report - ReportLab (see architecture-document.md
§2 for why WeasyPrint was dropped). Covers the brief's named requirements:
device identification, pass/fail findings with severity, and device-specific
remediation steps.
"""
import datetime as dt
import io
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_RESULT_COLORS = {
    "PASS": colors.HexColor("#059669"),
    "FAIL": colors.HexColor("#e11d48"),
    "NOT_EVALUATED": colors.HexColor("#64748b"),
}
_RESULT_LABELS = {"PASS": "Pass", "FAIL": "Fail", "NOT_EVALUATED": "Unknown"}
_SEVERITY_TINTS = {
    "CAT_I": colors.HexColor("#fee2e2"),
    "CAT_II": colors.HexColor("#fef3c7"),
    "CAT_III": colors.HexColor("#f1f5f9"),
}
_TIER_LABELS = {
    "tier1": "Instantly recognized",
    "tier2_accepted": "AI-classified",
    "tier3_human_confirmed": "Human-confirmed",
    None: "—",
}
_NAVY = colors.HexColor("#0f172a")
_NAVY_LIGHT = colors.HexColor("#1e293b")
_INDIGO = colors.HexColor("#4f46e5")
_MUTED = colors.HexColor("#64748b")
_BORDER = colors.HexColor("#e2e8f0")
_SEAL_GREEN = colors.HexColor("#059669")

PAGE_W, PAGE_H = letter

# Set once per generate() call so the header/footer callback (which ReportLab
# invokes per-page with no extra args of its own) can stamp the same report
# id and generation time on every page without threading them through
# SimpleDocTemplate's page callbacks.
_current_report_meta = {"report_id": "", "generated_at": ""}

# Fixed-offset last resort - zero dependency on the tzdata database, so this
# can never fail the way ZoneInfo(...) can (e.g. the `tzdata` PyPI package
# missing on Windows, which has no OS-level tz database of its own - the bug
# that motivated this whole fallback chain: both the requested zone AND the
# old ZoneInfo("Asia/Kolkata") fallback raised ZoneInfoNotFoundError
# identically, since they're the same mechanism).
_IST_FIXED_OFFSET = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")


def _resolve_zone(tz_name: str | None):
    for candidate in (tz_name, "Asia/Kolkata"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return _IST_FIXED_OFFSET


def generate(
    device: dict,
    evaluation: dict,
    framework_label: str | None = None,
    report_id: str | None = None,
    tz_name: str | None = None,
) -> bytes:
    # Stamped in the viewer's own clock, not the server's - the frontend
    # passes its browser-detected IANA zone (Intl.DateTimeFormat().resolvedOptions().timeZone),
    # so no IP/location lookup is ever involved. Falls back to IST since
    # that's this team's own timezone and the most likely default deployment.
    zone = _resolve_zone(tz_name)
    generated_at = dt.datetime.now(zone)
    tz_label = generated_at.tzname() or getattr(zone, "key", "IST")
    rid = f"AEGIS-{(report_id or evaluation.get('config_id') or '00000000')[:8].upper()}"
    _current_report_meta["report_id"] = rid
    _current_report_meta["generated_at"] = generated_at.strftime(f"%Y-%m-%d %H:%M {tz_label}")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=1.15 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        "AegisHeading", parent=styles["Heading2"], textColor=_NAVY, spaceBefore=4, spaceAfter=6,
    )
    story = []

    # Authenticity seal - directly answers "is this really an AEGIS output":
    # a bordered badge naming the report id, generation time, and the fact
    # that findings trace back to a hash-chained audit log (architecture
    # §4) rather than a claim with nothing behind it.
    seal_style = ParagraphStyle("seal", parent=styles["Normal"], fontSize=8, textColor=_SEAL_GREEN, leading=11)
    seal_table = Table(
        [[Paragraph(
            f"<b>&#10003; AEGIS VERIFIED OUTPUT</b> &nbsp;·&nbsp; Report ID {rid} &nbsp;·&nbsp; "
            f"Generated {_current_report_meta['generated_at']} &nbsp;·&nbsp; "
            f"Findings trace to a tamper-evident, hash-chained audit log",
            seal_style,
        )]],
        colWidths=[6.6 * inch],
    )
    seal_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, _SEAL_GREEN),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(seal_table)
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Device Identification", heading_style))
    id_rows = [
        ["Hostname", device.get("hostname") or "not available"],
        ["Vendor", device.get("vendor") or "unknown"],
        ["Model", device.get("model") or "not available"],
        ["Firmware / Version", device.get("firmware_version") or "not available"],
        ["Serial Number", device.get("serial_number") or "not available (not present in this config export)"],
    ]
    id_table = Table(id_rows, colWidths=[1.6 * inch, 4.9 * inch])
    id_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, _BORDER),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 0.3 * inch))

    counts = evaluation["counts"]
    story.append(Paragraph("Summary", heading_style))
    if framework_label:
        story.append(Paragraph(f"Framework: <b>{_escape(framework_label)}</b>", styles["Normal"]))
        story.append(Spacer(1, 0.08 * inch))

    stat_box_style = ParagraphStyle("stat", parent=styles["Normal"], alignment=1, textColor=colors.white)
    stat_num_style = ParagraphStyle("statnum", parent=stat_box_style, fontSize=20, fontName="Helvetica-Bold", leading=24)
    stat_label_style = ParagraphStyle("statlabel", parent=stat_box_style, fontSize=8, leading=10)

    def stat_cell(n, label, color):
        return [Paragraph(str(n), stat_num_style), Paragraph(label, stat_label_style)]

    stats_table = Table(
        [[
            stat_cell(counts["PASS"], "PASSED", _RESULT_COLORS["PASS"]),
            stat_cell(counts["FAIL"], "FAILED &mdash; NEEDS FIXING", _RESULT_COLORS["FAIL"]),
            stat_cell(counts["NOT_EVALUATED"], "COULD NOT BE EVALUATED", _RESULT_COLORS["NOT_EVALUATED"]),
        ]],
        colWidths=[2.17 * inch] * 3, rowHeights=[0.65 * inch],
    )
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), _RESULT_COLORS["PASS"]),
        ("BACKGROUND", (1, 0), (1, 0), _RESULT_COLORS["FAIL"]),
        ("BACKGROUND", (2, 0), (2, 0), _RESULT_COLORS["NOT_EVALUATED"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(stats_table)
    story.append(Paragraph(
        "A finding marked \"could not be evaluated\" means AEGIS did not have enough information to "
        "determine compliance for that control &mdash; this is never treated the same as a pass.",
        ParagraphStyle("note", parent=styles["Normal"], fontSize=7.5, textColor=_MUTED, spaceBefore=4),
    ))
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Compliance Findings", heading_style))
    header = ["Result", "Control", "Framework / ID", "Severity", "Source", "Remediation"]
    rows = [header]
    for f in evaluation["findings"]:
        rem = f.get("remediation") or ("no template available" if f["result"] == "FAIL" else "")
        rows.append([
            _RESULT_LABELS.get(f["result"], f["result"]),
            Paragraph(_escape(f.get("title") or f["rule_id"]), styles["BodyText"]),
            f"{f['framework']} / {f['rule_id']}",
            f["severity"],
            _TIER_LABELS.get(f.get("confidence_tier"), "—"),
            Paragraph(_escape(rem).replace("\n", "<br/>"), styles["BodyText"]),
        ])

    findings_table = Table(
        rows,
        colWidths=[0.6 * inch, 1.5 * inch, 1.05 * inch, 0.55 * inch, 0.85 * inch, 1.95 * inch],
        repeatRows=1,
    )
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]
    for i, f in enumerate(evaluation["findings"], start=1):
        style_cmds.append(("TEXTCOLOR", (0, i), (0, i), _RESULT_COLORS.get(f["result"], colors.black)))
        style_cmds.append(("FONTNAME", (0, i), (0, i), "Helvetica-Bold"))
        tint = _SEVERITY_TINTS.get(f["severity"])
        if tint:
            style_cmds.append(("BACKGROUND", (3, i), (3, i), tint))
    findings_table.setStyle(TableStyle(style_cmds))
    story.append(findings_table)

    story.append(Spacer(1, 0.25 * inch))
    disclaimer_style = ParagraphStyle("disclaimer", parent=styles["Normal"], fontSize=7.5, textColor=_MUTED)
    story.append(Paragraph(
        "Remediation commands above are drafted from known-good templates and have not been tested "
        "against a live device. Verify in a non-production environment before applying. \"Source\" shows "
        "how each finding's underlying setting was determined: instantly recognized from a previously "
        "learned pattern, classified automatically by AI, or confirmed by a human reviewer.",
        disclaimer_style,
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


def _draw_shield(canvas, x, y, w, h, fill_color):
    """Small shield glyph - a flat-top, single-point-bottom pentagon - drawn
    as the AEGIS mark next to the wordmark. Kept as plain line segments
    rather than a font glyph so it renders identically regardless of what
    fonts are installed on the machine building the PDF."""
    path = canvas.beginPath()
    path.moveTo(x, y + h)
    path.lineTo(x + w, y + h)
    path.lineTo(x + w, y + h * 0.42)
    path.lineTo(x + w / 2, y)
    path.lineTo(x, y + h * 0.42)
    path.close()
    canvas.setFillColor(fill_color)
    canvas.drawPath(path, fill=1, stroke=0)


def _header_footer(canvas, doc):
    canvas.saveState()

    # Watermark - very light, rotated wordmark behind the body content, on
    # every page. This is the "did this really come from AEGIS" mark: it
    # can't be produced by copy-pasting text into a blank document.
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 70)
    canvas.setFillColor(colors.HexColor("#0f172a"))
    canvas.setFillAlpha(0.035)
    canvas.translate(PAGE_W / 2, PAGE_H / 2)
    canvas.rotate(38)
    canvas.drawCentredString(0, 0, "AEGIS")
    canvas.restoreState()

    # Header band
    canvas.setFillColor(_NAVY)
    canvas.rect(0, PAGE_H - 0.75 * inch, PAGE_W, 0.75 * inch, fill=1, stroke=0)
    _draw_shield(canvas, 0.7 * inch, PAGE_H - 0.56 * inch, 0.24 * inch, 0.32 * inch, colors.white)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(1.08 * inch, PAGE_H - 0.48 * inch, "AEGIS")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#c7d2fe"))
    canvas.drawString(1.08 * inch, PAGE_H - 0.63 * inch, "Compliance Report")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#c7d2fe"))
    canvas.drawRightString(
        PAGE_W - 0.7 * inch, PAGE_H - 0.48 * inch,
        f"Generated {_current_report_meta['generated_at']}",
    )
    canvas.drawRightString(
        PAGE_W - 0.7 * inch, PAGE_H - 0.63 * inch,
        f"Report ID {_current_report_meta['report_id']}",
    )

    # Footer
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.7 * inch, 0.42 * inch, "AEGIS — Automated Evaluation & Governance for Infrastructure Security")
    canvas.drawRightString(PAGE_W - 0.7 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.setFont("Helvetica", 7)
    canvas.drawString(0.7 * inch, 0.28 * inch, f"Report ID {_current_report_meta['report_id']} — verify against the AEGIS audit log before acting on findings")
    canvas.restoreState()


def _escape(text) -> str:
    """ReportLab's Paragraph parses a small HTML-like markup subset - user/
    config-derived text (a remediation string, a rule title) must be escaped
    before going into one, or literal '<', '&', etc. from real config content
    could break rendering or be misinterpreted as markup."""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
