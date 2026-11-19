"""Generate clearly non-official identity-information documents with the returned portrait.

These outputs are personal information summaries, not Fayda ID cards or credentials.
They intentionally do not reproduce government card layouts, logos, seals, QR codes,
barcodes, expiry dates, or security features.
"""
from __future__ import annotations

import base64
import binascii
import re
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image as PDFImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DISCLAIMER = "NOT AN OFFICIAL IDENTITY DOCUMENT"
NAVY = "#12304A"
MUTED = "#526579"


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


def _photo_image(identity: dict) -> Image.Image | None:
    """Decode a photo returned in the identity response; never fetch arbitrary URLs."""
    value = identity.get("photo")
    if isinstance(value, dict):
        value = value.get("value") or value.get("data") or value.get("base64") or ""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("data:"):
        try:
            value = value.split(",", 1)[1]
        except IndexError:
            return None
    # Accept plain base64 only. A URL or other text is not treated as image data.
    value = re.sub(r"\\s+", "", value)
    try:
        raw = base64.b64decode(value, validate=False)
        if not raw or len(raw) > 8 * 1024 * 1024:
            return None
        image = Image.open(BytesIO(raw))
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")
    except (binascii.Error, OSError, ValueError):
        return None


def _photo_png(identity: dict, size: tuple[int, int]) -> BytesIO | None:
    photo = _photo_image(identity)
    if photo is None:
        return None
    photo = ImageOps.fit(photo, size, method=Image.Resampling.LANCZOS)
    output = BytesIO()
    photo.save(output, format="PNG")
    output.seek(0)
    return output


def render_identity_pdf(identity: dict) -> bytes:
    """Create an A4 personal-data report with the returned portrait, not an ID card."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="Personal identity information",
        author="FAYDA ID BOT",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ProfileTitle", parent=styles["Title"], textColor=colors.HexColor(NAVY),
        fontSize=20, leading=24, alignment=0, spaceAfter=3 * mm,
    )
    warning = ParagraphStyle(
        "Disclaimer", parent=styles["Heading2"], textColor=colors.HexColor("#9B1C1C"),
        fontSize=9, leading=12, alignment=1, spaceAfter=5 * mm,
    )
    body = ParagraphStyle("ProfileBody", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("ProfileSmall", parent=body, textColor=colors.HexColor(MUTED), fontSize=8)

    story = [
        Paragraph("Fayda Identity Information", title),
        Paragraph(DISCLAIMER, warning),
        Paragraph(
            "A personal copy of information returned during an authenticated Fayda data request. "
            "This report is not a government-issued identity card or proof of identity.",
            body,
        ),
        Spacer(1, 7 * mm),
    ]

    photo_buffer = _photo_png(identity, (360, 440))
    name = _english(identity.get("fullName")) or "Name not provided"
    if photo_buffer:
        portrait = PDFImage(photo_buffer, width=35 * mm, height=43 * mm)
        header = Table(
            [[Paragraph(f"<b>{name}</b><br/><font color='{MUTED}'>Personal identity information</font>", body), portrait]],
            colWidths=[130 * mm, 38 * mm],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#C8D4DF")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([header, Spacer(1, 6 * mm)])

    rows = [[Paragraph("<b>Information</b>", body), Paragraph("<b>Value</b>", body)]]
    for label, value in _fields(identity):
        safe = (value or "Not provided").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append([Paragraph(label, body), Paragraph(safe, body)])
    table = Table(rows, colWidths=[58 * mm, 110 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1F8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D4DF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([
        table,
        Spacer(1, 7 * mm),
        Paragraph(
            "This personal report does not replace an official Fayda document. "
            "No official card, QR code, barcode, expiry date, or security feature is generated.",
            small,
        ),
    ])
    doc.build(story)
    return output.getvalue()


def render_printable_summary_png(identity: dict) -> bytes:
    """Create a clean printable personal-information sheet with a photo when supplied."""
    width, height = 1600, 1100
    image = Image.new("RGB", (width, height), "#F3F6FA")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
        label_font = ImageFont.truetype("DejaVuSans.ttf", 25)
        value_font = ImageFont.truetype("DejaVuSans.ttf", 27)
        warning_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 23)
        name_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 35)
        small_font = ImageFont.truetype("DejaVuSans.ttf", 19)
    except OSError:
        title_font = label_font = value_font = warning_font = name_font = small_font = ImageFont.load_default()

    draw.rounded_rectangle((28, 28, width - 28, height - 28), radius=30, fill="white", outline="#C8D4DF", width=3)
    draw.rounded_rectangle((50, 50, width - 50, 170), radius=20, fill=NAVY)
    draw.text((85, 88), "FAYDA IDENTITY INFORMATION", font=title_font, fill="white")
    draw.rounded_rectangle((65, 195, width - 65, 260), radius=12, fill="#FCE8E8")
    draw.text((88, 212), DISCLAIMER, font=warning_font, fill="#9B1C1C")

    photo = _photo_image(identity)
    if photo is not None:
        photo = ImageOps.fit(photo, (260, 310), method=Image.Resampling.LANCZOS)
        image.paste(photo, (width - 355, 305))
        draw.rounded_rectangle((width - 355, 305, width - 95, 615), radius=12, outline="#C8D4DF", width=3)
    draw.text((85, 315), _english(identity.get("fullName")) or "Name not provided", font=name_font, fill=NAVY)
    draw.text((85, 370), "Personal identity information copy", font=small_font, fill=MUTED)

    fields = _fields(identity)
    y = 455
    for label, value in fields:
        if not value:
            continue
        draw.text((90, y), label.upper(), font=label_font, fill=MUTED)
        draw.text((600, y), value[:52], font=value_font, fill="#14283B")
        y += 55
        if y > 950:
            break

    draw.line((80, 1000, width - 80, 1000), fill="#C8D4DF", width=2)
    draw.text(
        (85, 1020),
        "Not a government-issued ID. For an official document, use the authorized Fayda service.",
        font=small_font,
        fill="#9B1C1C",
    )
    out = BytesIO()
    image.save(out, format="PNG", dpi=(300, 300))
    return out.getvalue()
