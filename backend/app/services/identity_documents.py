"""Generate clearly non-official identity-information summaries.

These files are not Fayda ID cards and deliberately contain no government template,
logo, expiry date, QR code, barcode, security marks, or fabricated registration data.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DISCLAIMER = "NOT AN OFFICIAL IDENTITY DOCUMENT"


def _english(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("eng") or value.get("en") or "")
    return str(value or "")


def _fields(identity: dict) -> list[tuple[str, str]]:
    return [
        ("Full name", _english(identity.get("fullName"))),
        ("Date of birth", _english(identity.get("dateOfBirth"))),
        ("Gender", _english(identity.get("gender"))),
        ("Phone", str(identity.get("phone") or "")),
        ("Fayda number (if returned)", str(identity.get("uin") or "")),
        ("Region", _english(identity.get("region"))),
        ("Zone", _english(identity.get("zone"))),
        ("Woreda", _english(identity.get("woreda"))),
        ("Nationality / residence status", _english(identity.get("residenceStatus"))),
        ("Email", str(identity.get("email") or "")),
    ]


def render_identity_pdf(identity: dict) -> bytes:
    """Create an A4 personal-data summary, not an identity credential."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Personal identity data summary",
        author="FAYDA ID BOT",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "SummaryTitle", parent=styles["Title"], textColor=colors.HexColor("#12304A"),
        fontSize=19, leading=23, spaceAfter=5 * mm,
    )
    warning = ParagraphStyle(
        "Disclaimer", parent=styles["Heading2"], textColor=colors.HexColor("#9B1C1C"),
        fontSize=10, leading=14, alignment=1, spaceAfter=7 * mm,
    )
    body = ParagraphStyle("SummaryBody", parent=styles["BodyText"], fontSize=10, leading=14)
    rows = [[Paragraph("<b>Field</b>", body), Paragraph("<b>Value</b>", body)]]
    for label, value in _fields(identity):
        rows.append([Paragraph(label, body), Paragraph(value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or "Not provided", body)])
    table = Table(rows, colWidths=[58 * mm, 112 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1F8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#12304A")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D4DF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story = [
        Paragraph("Personal Identity Data Summary", title),
        Paragraph(DISCLAIMER, warning),
        Paragraph("This summary displays information returned during an authenticated identity-data request. It is not a government-issued card, proof of identity, or replacement for an official Fayda document.", body),
        Spacer(1, 8 * mm),
        table,
        Spacer(1, 8 * mm),
        Paragraph("No expiry date, QR code, barcode, or government security feature has been created or inferred.", styles["Italic"]),
    ]
    doc.build(story)
    return output.getvalue()


def render_printable_summary_png(identity: dict) -> bytes:
    """Create a simple printable information panel with a prominent disclaimer."""
    width, height = 1200, 760
    image = Image.new("RGB", (width, height), "#F5F8FC")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 34)
        label_font = ImageFont.truetype("DejaVuSans.ttf", 23)
        value_font = ImageFont.truetype("DejaVuSans.ttf", 25)
        warning_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 23)
    except OSError:
        title_font = label_font = value_font = warning_font = ImageFont.load_default()

    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=28, fill="white", outline="#C8D4DF", width=3)
    draw.rectangle((24, 24, width - 24, 135), fill="#12304A")
    draw.text((58, 52), "PERSONAL IDENTITY DATA SUMMARY", font=title_font, fill="white")
    draw.rounded_rectangle((55, 160, width - 55, 218), radius=12, fill="#FCE8E8")
    draw.text((75, 175), DISCLAIMER, font=warning_font, fill="#9B1C1C")

    fields = _fields(identity)
    y = 255
    for label, value in fields:
        if not value:
            continue
        draw.text((70, y), label.upper(), font=label_font, fill="#526579")
        safe_value = value[:58]
        draw.text((470, y), safe_value, font=value_font, fill="#14283B")
        y += 48
        if y > 690:
            break

    out = BytesIO()
    image.save(out, format="PNG", dpi=(300, 300))
    return out.getvalue()
