from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io

# Palet formal — monokrom, satu aksen gelap untuk heading
INK       = colors.HexColor("#1A1A1A")
MUTED     = colors.HexColor("#595959")
ACCENT    = colors.HexColor("#2C3E50")   # slate gelap, dipakai untuk judul & garis pembatas
LINE      = colors.HexColor("#D9D9D9")
HEADER_BG = colors.HexColor("#F2F2F2")
ROW_ALT   = colors.HexColor("#FAFAFA")


def generate_schedule_pdf(nama: str, kronotipe: str, skor_meq: int, jadwal: dict, hari_order: list[str]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2.2*cm, bottomMargin=2*cm,
        leftMargin=2.2*cm, rightMargin=2.2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom", parent=styles["Heading1"],
        fontSize=18, spaceAfter=4, textColor=ACCENT, fontName="Helvetica-Bold"
    )
    sub_style = ParagraphStyle(
        "SubCustom", parent=styles["Normal"],
        fontSize=9.5, textColor=MUTED, spaceAfter=16
    )
    day_style = ParagraphStyle(
        "DayCustom", parent=styles["Heading2"],
        fontSize=12, textColor=INK, fontName="Helvetica-Bold",
        spaceBefore=16, spaceAfter=6, borderPadding=0,
    )

    elements = []
    elements.append(Paragraph("Jadwal Belajar — ChronoStudy", title_style))
    elements.append(Paragraph(
        f"{nama}  |  Kronotipe: {kronotipe}  |  Skor MEQ: {skor_meq}",
        sub_style
    ))

    for hari in hari_order:
        if hari not in jadwal or not jadwal[hari]:
            continue

        elements.append(Paragraph(hari, day_style))

        data = [["Jam", "Mata Kuliah", "Energi Kognitif"]]
        for jam, mk, en, bl in sorted(jadwal[hari]):
            label = "Puncak" if en >= 75 else "Baik" if en >= 50 else "Sedang" if en >= 30 else "Santai"
            data.append([f"{jam:02d}.00", mk, f"{label} ({en}%)"])

        table = Table(data, colWidths=[2.5*cm, 8.5*cm, 4*cm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "Jadwal ini adalah rekomendasi berdasarkan ritme sirkadian dan tingkat kesulitan mata kuliah. "
        "Kamu tetap bebas menyesuaikan sesuai kebutuhan.",
        sub_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()