"""
Layout engine for the VC Business Review PDF skill.

Takes a plain-dict "report context" (see references/context_schema.md) and
renders it to a finished landscape PDF using reportlab. Chart PNGs must
already exist on disk (generate them with charts.py) before calling
build_report().

This module owns pixel-level layout only. It never invents numbers or
wording — every string it places comes verbatim from the context dict that
the skill's workflow (SKILL.md) assembles from the source file / the user.
"""

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

PAGE_W, PAGE_H = 960, 540  # points; 13.333 x 7.5 in (16:9), matches the deck aspect ratio
MARGIN = 44

NAVY = HexColor("#1E2761")
NAVY_SOFT = HexColor("#29294C")
ORANGE = HexColor("#FF6D05")
PURPLE = HexColor("#4F4F95")
GRAY = HexColor("#A5A5A5")
GREEN = HexColor("#1D9E75")
RED = HexColor("#C0392B")
CARD_BG = HexColor("#F3F4F8")
CARD_BG_DARK = HexColor("#2A3270")
TEXT_DARK = HexColor("#1A1A1A")
TEXT_MUTED = HexColor("#5F5E5A")
WHITE = HexColor("#FFFFFF")
LIGHT_GRAY_TEXT = HexColor("#C7C9DA")

FONT_BOLD = "Helvetica-Bold"
FONT_REG = "Helvetica"
FONT_OBL = "Helvetica-Oblique"


def _para(text, size=10.5, color=TEXT_DARK, leading=None, font=FONT_REG, align=TA_LEFT):
    style = ParagraphStyle(
        "p", fontName=font, fontSize=size, leading=leading or size * 1.35,
        textColor=color, alignment=align,
    )
    return Paragraph(text, style)


def _draw_para(c, text, x, y, w, h, **kwargs):
    """Draws a wrapped paragraph inside box (x, y, w, h) with y = TOP of box."""
    p = _para(text, **kwargs)
    _, used_h = p.wrap(w, h)
    p.drawOn(c, x, y - used_h)
    return used_h


def _measure_para_height(text, w, **kwargs):
    """Wrapped text height at width w, for sizing a box to its content before drawing."""
    p = _para(text, **kwargs)
    _, used_h = p.wrap(w, 10_000)
    return used_h


def _footer(c, left_text, page_num=None, dark=False):
    c.setFont(FONT_REG, 8.5)
    c.setFillColor(LIGHT_GRAY_TEXT if dark else TEXT_MUTED)
    c.drawString(MARGIN, 18, left_text)
    if page_num is not None:
        c.drawRightString(PAGE_W - MARGIN, 18, str(page_num))


def _eyebrow_title(c, eyebrow, title, dark=False):
    c.setFont(FONT_BOLD, 9.5)
    c.setFillColor(ORANGE)
    c.drawString(MARGIN, PAGE_H - 46, eyebrow.upper())
    c.setFont(FONT_BOLD, 19)
    c.setFillColor(WHITE if dark else NAVY)
    c.drawString(MARGIN, PAGE_H - 70, title)


def cover_page(c, ctx):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFont(FONT_BOLD, 15)
    c.setFillColor(ORANGE)
    c.drawString(MARGIN, PAGE_H - 150, ctx["client_name"].upper())

    c.setFont(FONT_BOLD, 34)
    c.setFillColor(WHITE)
    c.drawString(MARGIN, PAGE_H - 195, ctx["report_title"])

    c.setFont(FONT_REG, 13)
    c.setFillColor(LIGHT_GRAY_TEXT)
    c.drawString(MARGIN, PAGE_H - 225, ctx["subtitle"])

    stat_y = PAGE_H - 300
    stat_x = MARGIN
    for stat in ctx["cover_stats"]:
        c.setFont(FONT_BOLD, 26)
        c.setFillColor(ORANGE)
        c.drawString(stat_x, stat_y, stat["value"])
        c.setFont(FONT_BOLD, 8.5)
        c.setFillColor(LIGHT_GRAY_TEXT)
        c.drawString(stat_x, stat_y - 18, stat["label"].upper())
        stat_x += 210

    c.setFillColor(ORANGE)
    c.circle(MARGIN + 3, 48, 3, fill=1, stroke=0)
    c.setFont(FONT_REG, 9.5)
    c.setFillColor(LIGHT_GRAY_TEXT)
    c.drawString(MARGIN + 14, 44, f"Prepared by Vantage Circle  ·  {ctx['prepared_date']}")


def exec_summary_page(c, ctx):
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    _eyebrow_title(c, "Executive Summary", ctx["exec_summary"]["headline"])

    cards = ctx["exec_summary"]["kpi_cards"]
    n = len(cards)
    gap = 14
    card_w = (PAGE_W - 2 * MARGIN - gap * (n - 1)) / n
    card_h = 90
    card_y = PAGE_H - 190
    for i, card in enumerate(cards):
        cx = MARGIN + i * (card_w + gap)
        c.setFillColor(CARD_BG)
        c.roundRect(cx, card_y, card_w, card_h, 6, fill=1, stroke=0)
        c.setFont(FONT_BOLD, 20)
        c.setFillColor(ORANGE if card.get("accent", True) else NAVY)
        c.drawString(cx + 14, card_y + card_h - 34, card["value"])
        c.setFont(FONT_BOLD, 9.5)
        c.setFillColor(TEXT_DARK)
        c.drawString(cx + 14, card_y + card_h - 52, card["label"])
        _draw_para(c, card.get("sublabel", ""), cx + 14, card_y + card_h - 62,
                   card_w - 28, 40, size=8, color=TEXT_MUTED)

    box_y_top = card_y - 26
    box_h = 150
    c.setFillColor(NAVY)
    c.roundRect(MARGIN, box_y_top - box_h, PAGE_W - 2 * MARGIN, box_h, 8, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(ORANGE)
    c.drawString(MARGIN + 20, box_y_top - 28, ctx["exec_summary"]["callout_title"])

    ty = box_y_top - 50
    for bullet in ctx["exec_summary"]["bullets"]:
        c.setFillColor(ORANGE)
        c.circle(MARGIN + 24, ty - 4, 2.2, fill=1, stroke=0)
        used = _draw_para(c, bullet, MARGIN + 36, ty + 6,
                           PAGE_W - 2 * MARGIN - 60, 60, size=9.7, color=WHITE, leading=14)
        ty -= max(used, 16) + 8

    _footer(c, ctx["footer_left"], ctx.get("page_num"))


def metric_page(c, ctx):
    """Generic deep-dive page: chart on the left, sidebar (text and/or stat boxes) on the right."""
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    _eyebrow_title(c, ctx["eyebrow"], ctx["title"])

    chart_x, chart_y = MARGIN, 70
    chart_w, chart_h = 500, 340
    if ctx.get("chart_path"):
        img = ImageReader(ctx["chart_path"])
        c.drawImage(img, chart_x, chart_y, width=chart_w, height=chart_h,
                    preserveAspectRatio=True, anchor="sw", mask="auto")

    side_x = MARGIN + chart_w + 30
    side_w = PAGE_W - MARGIN - side_x
    sy = PAGE_H - 110

    if ctx.get("sidebar_heading"):
        c.setFont(FONT_BOLD, 11.5)
        c.setFillColor(NAVY)
        c.drawString(side_x, sy, ctx["sidebar_heading"])
        sy -= 22

    for para in ctx.get("sidebar_text", []):
        used = _draw_para(c, para, side_x, sy, side_w, 90, size=9.7, color=TEXT_DARK, leading=14)
        sy -= used + 14

    for box in ctx.get("stat_boxes", []):
        body_text = box.get("body", "")
        measured = _measure_para_height(body_text, side_w - 28, size=8.3, leading=11.5)
        box_h = max(box.get("height", 64), 34 + measured + 12)
        sy -= 4
        c.setFillColor(HexColor(box.get("bg", "#F3F4F8")))
        c.roundRect(side_x, sy - box_h, side_w, box_h, 6, fill=1, stroke=0)
        c.setFont(FONT_BOLD, 17)
        c.setFillColor(HexColor(box.get("value_color", "#FF6D05")))
        c.drawString(side_x + 14, sy - 26, box["value"])
        _draw_para(c, body_text, side_x + 14, sy - 34,
                   side_w - 28, box_h - 30, size=8.3, color=TEXT_DARK, leading=11.5)
        sy -= box_h + 10

    if ctx.get("note"):
        measured = _measure_para_height(ctx["note"], side_w - 24, size=8.2, leading=11.5)
        note_h = max(40, measured + 28)
        sy -= 6
        c.setFillColor(NAVY_SOFT)
        c.roundRect(side_x, sy - note_h, side_w, note_h, 6, fill=1, stroke=0)
        _draw_para(c, ctx["note"], side_x + 12, sy - 14, side_w - 24, note_h - 16,
                   size=8.2, color=WHITE, leading=11.5)

    _footer(c, ctx["footer_left"], ctx.get("page_num"))


def comparison_page(c, ctx):
    """Chart + a metric/value/%change table, e.g. 'latest period vs. average'."""
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    _eyebrow_title(c, ctx["eyebrow"], ctx["title"])

    chart_x, chart_y = MARGIN, 70
    chart_w, chart_h = 440, 340
    if ctx.get("chart_path"):
        img = ImageReader(ctx["chart_path"])
        c.drawImage(img, chart_x, chart_y, width=chart_w, height=chart_h,
                    preserveAspectRatio=True, anchor="sw", mask="auto")

    side_x = MARGIN + chart_w + 30
    side_w = PAGE_W - MARGIN - side_x
    sy = PAGE_H - 110

    c.setFont(FONT_BOLD, 10.5)
    c.setFillColor(NAVY)
    c.drawString(side_x, sy, ctx.get("table_heading", ""))
    sy -= 20

    for row in ctx["rows"]:
        c.setFont(FONT_REG, 9.5)
        c.setFillColor(TEXT_DARK)
        c.drawString(side_x, sy, row["metric"])
        c.setFont(FONT_BOLD, 11)
        c.setFillColor(TEXT_DARK)
        c.drawRightString(side_x + side_w - 55, sy, row["value"])
        delta_color = GREEN if row.get("delta_positive") else RED
        c.setFillColor(delta_color)
        c.setFont(FONT_BOLD, 10)
        c.drawRightString(side_x + side_w, sy, row["delta"])
        c.setStrokeColor(HexColor("#E4E4EA"))
        c.line(side_x, sy - 8, side_x + side_w, sy - 8)
        sy -= 34

    if ctx.get("warning"):
        measured = _measure_para_height(ctx["warning"], side_w - 24, size=8.3, leading=11.8)
        note_h = max(50, measured + 30)
        sy -= 8
        c.setFillColor(NAVY)
        c.roundRect(side_x, sy - note_h, side_w, note_h, 6, fill=1, stroke=0)
        _draw_para(c, ctx["warning"], side_x + 12, sy - 16, side_w - 24, note_h - 20,
                   size=8.3, color=WHITE, leading=11.8)

    _footer(c, ctx["footer_left"], ctx.get("page_num"))


def closing_page(c, ctx):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 9.5)
    c.setFillColor(ORANGE)
    c.drawString(MARGIN, PAGE_H - 46, ctx["closing"]["eyebrow"].upper())
    c.setFont(FONT_BOLD, 22)
    c.setFillColor(WHITE)
    c.drawString(MARGIN, PAGE_H - 74, ctx["closing"]["title"])

    items = ctx["closing"]["items"]
    cols = 2
    gap_x, gap_y = 18, 16
    card_w = (PAGE_W - 2 * MARGIN - gap_x) / cols
    card_h = 92
    top_y = PAGE_H - 110

    for i, item in enumerate(items):
        row, col = divmod(i, cols)
        full_width = (len(items) - row * cols == 1)
        cx = MARGIN if not full_width else MARGIN
        cw = card_w if not full_width else (PAGE_W - 2 * MARGIN)
        if not full_width:
            cx = MARGIN + col * (card_w + gap_x)
        cy = top_y - row * (card_h + gap_y)

        c.setFillColor(CARD_BG_DARK)
        c.roundRect(cx, cy - card_h, cw, card_h, 8, fill=1, stroke=0)

        c.setFillColor(ORANGE)
        c.circle(cx + 28, cy - 26, 13, fill=1, stroke=0)
        c.setFont(FONT_BOLD, 12)
        c.setFillColor(WHITE)
        c.drawCentredString(cx + 28, cy - 30, str(item["num"]))

        c.setFont(FONT_BOLD, 12)
        c.setFillColor(WHITE)
        c.drawString(cx + 54, cy - 26, item["title"])
        _draw_para(c, item["body"], cx + 54, cy - 40, cw - 70, card_h - 44,
                   size=8.6, color=LIGHT_GRAY_TEXT, leading=11.8)

    c.setFillColor(ORANGE)
    c.circle(MARGIN + 3, 24, 3, fill=1, stroke=0)
    c.setFont(FONT_REG, 9)
    c.setFillColor(LIGHT_GRAY_TEXT)
    c.drawString(MARGIN + 14, 20, ctx["closing"]["footer"])


def build_report(ctx, out_path):
    """ctx: full report context dict (see references/context_schema.md). Writes out_path."""
    c = canvas.Canvas(out_path, pagesize=(PAGE_W, PAGE_H))

    cover_page(c, ctx)
    c.showPage()

    ctx["page_num"] = ctx["page_counter"]()
    exec_summary_page(c, ctx)
    c.showPage()

    for page in ctx["pages"]:
        page["footer_left"] = ctx["footer_left"]
        page["page_num"] = ctx["page_counter"]()
        if page.get("type") == "comparison":
            comparison_page(c, page)
        else:
            metric_page(c, page)
        c.showPage()

    closing_page(c, ctx)
    c.showPage()

    c.save()
