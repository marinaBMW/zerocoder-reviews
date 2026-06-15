"""Build corporate-style PPTX for the 2030 customer service pitch.

Uses Zerocoder brand palette and logo extracted from reference deck.
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from copy import deepcopy
from lxml import etree

PROJECT = Path(__file__).parent.parent
ASSETS = PROJECT / 'tmp' / 'assets'
OUTPUT = PROJECT / 'reports' / '2026-06-03-pitch-customer-service-2030.pptx'

# Brand palette (eyeballed from reference)
PURPLE = RGBColor(0xA2, 0x8F, 0xF5)
PURPLE_DARK = RGBColor(0x6E, 0x57, 0xCC)
GREEN = RGBColor(0x5C, 0xE2, 0xA0)
DARK = RGBColor(0x1F, 0x1E, 0x2E)
DARK_BODY = RGBColor(0x33, 0x33, 0x44)
LAVENDER_BG = RGBColor(0xEC, 0xE2, 0xFC)
LAVENDER_LIGHT = RGBColor(0xF6, 0xF0, 0xFF)
GREY_FOOTER = RGBColor(0x7A, 0x7A, 0x8A)
GREY_LINE = RGBColor(0xC8, 0xC8, 0xD0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

HEAD_FONT = 'Montserrat'
BODY_FONT = 'Manrope'


def set_run(run, text, font=BODY_FONT, size=14, color=DARK_BODY, bold=False):
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold


def add_text(slide, text, x, y, w, h, font=BODY_FONT, size=14, color=DARK_BODY,
             bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Add a single-run textbox."""
    tx = slide.shapes.add_textbox(x, y, w, h)
    tf = tx.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    set_run(run, text, font, size, color, bold)
    return tx


def add_logo(slide, prs):
    """Logo in top-right corner."""
    slide.shapes.add_picture(
        str(ASSETS / 'logo.png'),
        prs.slide_width - Inches(0.85),
        Inches(0.4),
        height=Inches(0.55),
    )


def add_footer(slide, prs):
    """Footer: thin lines + zerocoder.ru, centered."""
    cx = prs.slide_width / 2
    y_line = Inches(7.18)
    # left line
    l1 = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                     cx - Inches(1.2), y_line,
                                     cx - Inches(0.55), y_line)
    l1.line.color.rgb = GREY_LINE
    l1.line.width = Pt(0.6)
    # right line
    l2 = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                     cx + Inches(0.55), y_line,
                                     cx + Inches(1.2), y_line)
    l2.line.color.rgb = GREY_LINE
    l2.line.width = Pt(0.6)
    # text
    add_text(slide, 'zerocoder.ru',
             cx - Inches(0.55), Inches(7.05),
             Inches(1.1), Inches(0.3),
             font=BODY_FONT, size=10, color=GREY_FOOTER,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def add_chrome(slide, prs):
    add_logo(slide, prs)
    add_footer(slide, prs)


def add_rounded_block(slide, x, y, w, h, fill=LAVENDER_BG, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.adjustments[0] = 0.08  # rounding
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line:
        shape.line.color.rgb = line
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def make_table(slide, x, y, w, h, rows, cols,
               header_fill=PURPLE, header_text=WHITE,
               body_fill=WHITE, body_text=DARK_BODY,
               alt_fill=LAVENDER_LIGHT):
    """Create a styled table, return table object."""
    tbl_shape = slide.shapes.add_table(rows, cols, x, y, w, h)
    tbl = tbl_shape.table
    return tbl


def style_cell(cell, text, font=BODY_FONT, size=11, color=DARK_BODY,
               bold=False, align=PP_ALIGN.LEFT, fill=None, anchor=MSO_ANCHOR.MIDDLE,
               runs=None):
    """Style a single cell. runs = list of (text, kwargs) for multi-run."""
    if fill is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
    tf = cell.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.05)
    tf.margin_bottom = Inches(0.05)
    cell.vertical_anchor = anchor
    # Clear default paragraph
    p = tf.paragraphs[0]
    p.alignment = align
    if runs is not None:
        # multi-run
        if p.runs:
            # remove first run? just use as first
            r = p.runs[0]
            r.text = ''
        for i, (t, kw) in enumerate(runs):
            r = p.add_run()
            set_run(r,
                    t,
                    font=kw.get('font', font),
                    size=kw.get('size', size),
                    color=kw.get('color', color),
                    bold=kw.get('bold', bold))
    else:
        r = p.add_run()
        set_run(r, text, font, size, color, bold)


def remove_cell_borders(cell):
    """Make cell borders invisible (mostly)."""
    tcPr = cell._tc.get_or_add_tcPr()
    for border_name in ('a:lnL', 'a:lnR', 'a:lnT', 'a:lnB'):
        nsmap = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        existing = tcPr.findall(qn(border_name.replace('a:', 'a:')), nsmap)
        for el in existing:
            tcPr.remove(el)
        ln = etree.SubElement(tcPr, qn(border_name))
        ln.set('w', '6350')
        ln.set('cap', 'flat')
        ln.set('cmpd', 'sng')
        ln.set('algn', 'ctr')
        solidFill = etree.SubElement(ln, qn('a:solidFill'))
        srgb = etree.SubElement(solidFill, qn('a:srgbClr'))
        srgb.set('val', 'E5E5EC')


# ──────────────────────────────────────────────────────────────────────────────
# Build presentation
# ──────────────────────────────────────────────────────────────────────────────

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]


# ─── Slide 1: Cover ───────────────────────────────────────────────────────────
s1 = prs.slides.add_slide(BLANK)
# background already white

# Title in purple/green stack
tx = s1.shapes.add_textbox(Inches(0.7), Inches(1.4), Inches(7.5), Inches(4.5))
tf = tx.text_frame
tf.word_wrap = True
tf.margin_left = 0
tf.margin_top = 0
p1 = tf.paragraphs[0]
p1.alignment = PP_ALIGN.LEFT
r1 = p1.add_run()
set_run(r1, 'Клиентский', font=HEAD_FONT, size=58, color=PURPLE, bold=True)
p2 = tf.add_paragraph()
r2 = p2.add_run()
set_run(r2, 'сервис', font=HEAD_FONT, size=58, color=PURPLE, bold=True)
p3 = tf.add_paragraph()
r3 = p3.add_run()
set_run(r3, 'Zerocoder', font=HEAD_FONT, size=58, color=GREEN, bold=True)
p4 = tf.add_paragraph()
r4 = p4.add_run()
set_run(r4, 'в 2030', font=HEAD_FONT, size=58, color=GREEN, bold=True)

# Underscore accent
acc = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                           Inches(0.7), Inches(5.85),
                           Inches(0.5), Inches(0.08))
acc.fill.solid()
acc.fill.fore_color.rgb = GREEN
acc.line.fill.background()
acc.shadow.inherit = False

# Subtitle
add_text(s1,
         'Из статьи расходов — в инвестицию,\nкоторая приносит выручку каждый месяц',
         Inches(0.7), Inches(6.0), Inches(7.5), Inches(1.0),
         font=BODY_FONT, size=18, color=DARK_BODY)

# Cover illustration on right
s1.shapes.add_picture(str(ASSETS / 'cover-illustration.png'),
                       Inches(7.5), Inches(1.5),
                       width=Inches(5.4))

add_chrome(s1, prs)




# Save
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT2 = OUTPUT.parent / "test-slide1-only.pptx"
prs.save(str(OUTPUT2))
print("saved", OUTPUT2)
