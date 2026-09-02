"""PDF renderer (reportlab / platypus). Pure-python, no system deps — safe in the slim image."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ASSETS = Path(__file__).parent / "assets"

NAVY = colors.HexColor("#0b1020")
ACCENT = colors.HexColor("#2f6fed")
MUTED = colors.HexColor("#6b7390")
LINE = colors.HexColor("#d9deea")
SEV = {"high": colors.HexColor("#d64545"), "medium": colors.HexColor("#d98b1e"), "low": colors.HexColor("#3a9d6a")}
SEV_BG = {"high": colors.HexColor("#fdecec"), "medium": colors.HexColor("#fff4e3"), "low": colors.HexColor("#e9f7ef")}


def _styles():
    ss = getSampleStyleSheet()
    base = ss["BodyText"]
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=NAVY, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base, fontSize=10, textColor=MUTED, leading=13),
        "h": ParagraphStyle("h", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, textColor=NAVY, spaceBefore=12, spaceAfter=6, keepWithNext=True),
        "headline": ParagraphStyle("hl", parent=base, fontName="Helvetica-Bold", fontSize=12.5, leading=17, textColor=NAVY, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base, fontSize=10, leading=14.5, spaceAfter=6),
        "small": ParagraphStyle("sm", parent=base, fontSize=8.5, leading=11.5, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base, fontSize=8.8, leading=11.5),
        "cellb": ParagraphStyle("cb", parent=base, fontName="Helvetica-Bold", fontSize=8.8, leading=11.5),
        "kpi_n": ParagraphStyle("kn", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=20, textColor=NAVY),
        "kpi_l": ParagraphStyle("kl", parent=base, fontSize=8, leading=10, textColor=MUTED),
    }


def _esc(s: Any) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _kpi_strip(k: dict[str, Any], st) -> Table:
    cells = [
        (k["changes"], "changes detected"),
        (k["high"], "high severity"),
        (k["insights"], "AI insights"),
        (k["actions"], "recommended actions"),
        (k["competitors"], "competitors"),
        (k["keywords"], "keywords"),
    ]
    tiles = [Table([[Paragraph(str(n), st["kpi_n"])], [Paragraph(lbl, st["kpi_l"])]], colWidths=[1.1 * inch]) for n, lbl in cells]
    t = Table([tiles], colWidths=[1.2 * inch] * 6)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _table(rows: list[list[Any]], widths, header=True, sev_col: int | None = None) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY if header else LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if sev_col is not None:
        for i, r in enumerate(rows[1:], start=1):
            sev = str(r[sev_col].text if hasattr(r[sev_col], "text") else r[sev_col]).lower()
            if sev in SEV_BG:
                style.append(("BACKGROUND", (sev_col, i), (sev_col, i), SEV_BG[sev]))
                style.append(("TEXTCOLOR", (sev_col, i), (sev_col, i), SEV[sev]))
    t.setStyle(TableStyle(style))
    return t


def _demand_chart(keywords: list[dict[str, Any]]) -> Drawing | None:
    series = [k for k in keywords if len(k.get("demand_series") or []) >= 3][:3]
    if not series:
        return None
    d = Drawing(460, 150)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 40, 22, 400, 110
    lp.data = [[(i, p["value"]) for i, p in enumerate(k["demand_series"])] for k in series]
    palette = [ACCENT, colors.HexColor("#d98b1e"), colors.HexColor("#3a9d6a")]
    for i, _ in enumerate(series):
        lp.lines[i].strokeColor = palette[i % 3]
        lp.lines[i].strokeWidth = 1.6
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, 100
    lp.yValueAxis.valueStep = 25
    lp.xValueAxis.visibleLabels = 0
    lp.yValueAxis.labels.fontSize = 7
    d.add(lp)
    x = 40
    for i, k in enumerate(series):
        d.add(String(x, 6, f"— {k['term']}", fontSize=7.5, fillColor=palette[i % 3]))
        x += 140
    return d


def render_pdf(data: dict[str, Any]) -> bytes:
    st = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title=f"AdWatch — {data['title']}", author="AdWatch")
    w, _ = doc.width, doc.height
    story: list[Any] = []

    # header
    logo = ASSETS / "logo-light.png"
    hdr = [[Image(str(logo), width=1.7 * inch, height=0.425 * inch) if logo.exists() else Paragraph("AdWatch", st["title"]), Paragraph(f"{_esc(data['watchlist']['name'])} · {_esc(data['watchlist']['vertical'])} · {_esc(data['watchlist']['geo'])}<br/>{data['period']['from']} → {data['period']['to']} · generated {data['generated_at'].replace('T', ' ')} UTC", st["sub"])]]
    t = Table(hdr, colWidths=[2.0 * inch, w - 2.0 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("LINEBELOW", (0, 0), (-1, 0), 1, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [t, Spacer(1, 10), Paragraph(_esc(data["title"]), st["title"]), Paragraph(f"Prepared for {_esc(data['audience'].upper() if data['audience'] == 'cfo' else 'Marketing')} · {data['kpis']['runs_in_period']} collection runs in period", st["sub"]), Spacer(1, 10)]
    story += [_kpi_strip(data["kpis"], st), Spacer(1, 12)]

    # executive summary
    ex = data["executive_summary"]
    story.append(Paragraph("Executive summary", st["h"]))
    story.append(Paragraph(_esc(ex.get("headline", "")), st["headline"]))
    for p in ex.get("paragraphs", []):
        story.append(Paragraph(_esc(p), st["body"]))
    if ex.get("decisions"):
        story.append(Paragraph("<b>Decisions for this reader</b>", st["body"]))
        for d_ in ex["decisions"]:
            story.append(Paragraph("• " + _esc(d_), st["body"]))
    if ex.get("watch_next"):
        story.append(Paragraph("<b>Watch next:</b> " + _esc(ex["watch_next"]), st["body"]))

    # actions
    if data["actions"]:
        story.append(Paragraph("Recommended actions", st["h"]))
        rows = [[Paragraph(x, st["cellb"]) for x in ("Urgency", "Effort", "Action", "Rationale")]]
        for a in data["actions"]:
            rows.append([Paragraph(_esc(a.get("urgency", "")).replace("_", " "), st["cell"]), Paragraph(_esc(a.get("effort", "")), st["cell"]), Paragraph(_esc(a.get("action", "")), st["cell"]), Paragraph(_esc(a.get("rationale", "")), st["cell"])])
        story.append(_table(rows, [0.8 * inch, 0.6 * inch, 2.6 * inch, w - 4.0 * inch]))

    # changes
    story.append(PageBreak())
    story.append(Paragraph(f"What changed ({data['kpis']['changes']} events)", st["h"]))
    if data["changes_by_kind"]:
        story.append(Paragraph(" · ".join(f"{c['count']} {c['label'].lower()}" for c in data["changes_by_kind"]), st["small"]))
        story.append(Spacer(1, 6))
    rows = [[Paragraph(x, st["cellb"]) for x in ("Sev", "Type", "Subject", "Detail")]]
    for c in data["changes"]:
        rows.append([Paragraph(c["severity"], st["cellb"]), Paragraph(_esc(c["label"]), st["cell"]), Paragraph(_esc(c["subject"]), st["cell"]), Paragraph(_esc(c["description"]), st["cell"])])
    if len(rows) == 1:
        rows.append([Paragraph("—", st["cell"]), Paragraph("No changes detected in the period", st["cell"]), "", ""])
    story.append(_table(rows, [0.75 * inch, 1.45 * inch, 1.3 * inch, w - 3.5 * inch], sev_col=0))

    # competitors
    story.append(Paragraph("Competitor activity", st["h"]))
    rows = [[Paragraph(x, st["cellb"]) for x in ("Competitor", "Domain", "Active", "Launched", "Dropped", "Formats")]]
    for c in data["competitors"]:
        fmts = ", ".join(f"{k} {v}" for k, v in sorted(c["formats"].items()))
        rows.append([Paragraph(_esc(c["name"]), st["cell"]), Paragraph(_esc(c["domain"]), st["cell"]), Paragraph(str(c["active_creatives"]), st["cell"]), Paragraph(str(c["launched"]), st["cell"]), Paragraph(str(c["dropped"]), st["cell"]), Paragraph(_esc(fmts), st["cell"])])
    story.append(_table(rows, [1.3 * inch, 1.6 * inch, 0.7 * inch, 0.85 * inch, 0.8 * inch, w - 5.25 * inch]))

    # keywords
    story.append(Paragraph("Keywords: paid block, share of voice, demand", st["h"]))
    chart = _demand_chart(data["keywords"])
    if chart:
        story += [chart, Paragraph("Google Trends interest over time (0–100), latest collection.", st["small"]), Spacer(1, 6)]
    for k in data["keywords"]:
        block = ", ".join(f"{'↓' if a['block'] == 'bottom' else ''}#{a['position']} {a['domain']}{' *' if a['tracked'] else ''}" for a in k["paid_block"]) or "no paid results captured"
        sov = ", ".join(f"{s['domain']} ×{s['appearances']} (avg #{s['avg_position']})" for s in k["share_of_voice"][:4]) or "—"
        demand = f"{k['demand_latest']}" + (f" vs 4-wk avg {k['demand_trailing']}" if k["demand_trailing"] is not None else "") if k["demand_latest"] is not None else "—"
        rising = ", ".join(k["rising_queries"]) or "—"
        blk = [
            Paragraph(f"<b>{_esc(k['term'])}</b>", st["body"]),
            Paragraph(f"<b>Paid block now:</b> {_esc(block)}", st["cell"]),
            Paragraph(f"<b>Share of voice (all runs):</b> {_esc(sov)}", st["cell"]),
            Paragraph(f"<b>Demand:</b> {_esc(demand)} &nbsp;&nbsp; <b>Rising:</b> {_esc(rising)}", st["cell"]),
            Spacer(1, 6),
        ]
        story.append(KeepTogether(blk))
    story.append(Paragraph("* tracked competitor. Source: SerpApi (Google Ads Transparency Center, Google Search, Google Trends). Analysis: AdWatch diff engine + AI analyst.", st["small"]))

    doc.build(story)
    return buf.getvalue()
