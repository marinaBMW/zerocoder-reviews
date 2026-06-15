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
    cx = prs.slide_width // 2
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


# ─── Slide 2: 5 уровней сопровождения ─────────────────────────────────────────
s2 = prs.slides.add_slide(BLANK)

# Heading
add_text(s2, 'Пять уровней сопровождения',
         Inches(0.7), Inches(0.5), Inches(11), Inches(0.8),
         font=HEAD_FONT, size=32, color=PURPLE, bold=True)

# Table: 5 columns of tariffs, 5 rows (header + 4 attribute rows)
tariffs = ['Базовый', 'Бизнес', 'VIP', 'VIP+', 'Luxury']
rows_data = [
    ('Команда\nсопровождения', [
        'Только ИИ',
        'Продвинутый ИИ',
        '+ Архитектор\nтраектории',
        '+ Команда:\nархитектор,\nИИ-инженер,\nкарьерный',
        '+ Команда 3–5 чел\n+ топ-менеджмент',
    ]),
    ('Что в центре\nопыта', [
        'Структура\n+ первый агент',
        'ИИ ведёт\nкак наставник',
        'Гарантия\n+ помощь\nс заказами',
        'Личная\nмногоагентная\nинфраструктура',
        'Корпоративная\nтрансформация',
    ]),
    ('Доступ\nк сообществу', [
        'Поток\n+ общий канал',
        '+ Микро-круг\n+ ниша',
        '+ Клуб\nVIP-выпускников',
        '+ Нейроклуб Pro',
        '+ Нейроклуб\nInner Circle',
    ]),
    ('Гарантия\nрезультата', [
        '—',
        '—',
        'Возврат, если\nне вышел\nна окупаемость',
        'KPI в договоре',
        'Бизнес-KPI\nклиента',
    ]),
]

table_x = Inches(0.7)
table_y = Inches(1.5)
table_w = Inches(12.0)
table_h = Inches(4.7)

cols = 1 + len(tariffs)  # row label + 5 tariffs
rows = 1 + len(rows_data)  # header + attribute rows

tbl_shape = s2.shapes.add_table(rows, cols, table_x, table_y, table_w, table_h)
tbl = tbl_shape.table

# Column widths
tbl.columns[0].width = Inches(1.6)
each_w = Emu(int((table_w - Inches(1.6)) / 5))
for c in range(1, cols):
    tbl.columns[c].width = each_w

# Header row
hdr = tbl.rows[0]
hdr.height = Inches(0.6)
style_cell(hdr.cells[0], '', fill=WHITE)
for i, name in enumerate(tariffs, start=1):
    style_cell(hdr.cells[i], name,
               font=HEAD_FONT, size=16, color=WHITE, bold=True,
               align=PP_ALIGN.CENTER, fill=PURPLE_DARK)

# Data rows
for ri, (row_label, vals) in enumerate(rows_data, start=1):
    tbl.rows[ri].height = Inches(1.0)
    style_cell(tbl.rows[ri].cells[0], row_label,
               font=BODY_FONT, size=12, color=PURPLE_DARK, bold=True,
               align=PP_ALIGN.LEFT, fill=LAVENDER_LIGHT)
    for ci, v in enumerate(vals, start=1):
        fill = WHITE if ri % 2 == 1 else LAVENDER_LIGHT
        style_cell(tbl.rows[ri].cells[ci], v,
                   font=BODY_FONT, size=11, color=DARK_BODY,
                   align=PP_ALIGN.CENTER, fill=fill)

# Bottom callout
callout = add_rounded_block(s2, Inches(0.7), Inches(6.35),
                             Inches(12.0), Inches(0.6),
                             fill=LAVENDER_BG)
add_text(s2,
         'Живой человек — только в верхних трёх тарифах. ФОТ растёт с VIP-сегментом, не с базой клиентов.',
         Inches(0.7), Inches(6.35), Inches(12.0), Inches(0.6),
         font=BODY_FONT, size=14, color=PURPLE_DARK, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

add_chrome(s2, prs)


# ─── Slide 3: CJM Маши ────────────────────────────────────────────────────────
s3 = prs.slides.add_slide(BLANK)

add_text(s3, 'Как это ощущается студенту',
         Inches(0.7), Inches(0.5), Inches(11), Inches(0.6),
         font=HEAD_FONT, size=32, color=PURPLE, bold=True)
add_text(s3, 'Маша, маркетолог, хочет стать блогером в нише «нейросети для повседневных задач»',
         Inches(0.7), Inches(1.15), Inches(12), Inches(0.4),
         font=BODY_FONT, size=15, color=DARK_BODY)

cjm_rows = [
    ('Старт',
     'ИИ-интервью,\nиндивидуальный план под курс',
     '+ 1.5-час сессия с архитектором,\nплан на 12 мес до выхода на доход'),
    ('Просадка\nмотивации',
     'ИИ замечает по сигналам,\nинициирует разговор,\nперестраивает план',
     '+ Архитектор берёт внеочередную\nсессию в течение 24 часов\nпри кризисе'),
    ('Первое видео',
     'ИИ-агент: сценарий, превью,\nаналитика трендов',
     '+ Редакционные сессии\nс архитектором как с редактором'),
    ('Первый заказ\nот бренда',
     'ИИ помогает оценить\nи провести переговоры',
     '+ Архитектор лично разбирает\nкаждый первый заказ,\nпомогает торговаться'),
    ('После курса',
     'Подписка на агента\n+ сообщество',
     '+ Гарантия окупаемости 6 мес,\nклуб VIP-выпускников,\nменторство'),
]

ctab_x = Inches(0.7)
ctab_y = Inches(1.7)
ctab_w = Inches(12.0)
ctab_h = Inches(4.5)

cjm_shape = s3.shapes.add_table(len(cjm_rows) + 1, 3, ctab_x, ctab_y, ctab_w, ctab_h)
ctbl = cjm_shape.table
ctbl.columns[0].width = Inches(2.0)
ctbl.columns[1].width = Inches(5.0)
ctbl.columns[2].width = Inches(5.0)

# Header
hdr_c = ctbl.rows[0]
hdr_c.height = Inches(0.55)
style_cell(hdr_c.cells[0], 'Этап',
           font=HEAD_FONT, size=14, color=WHITE, bold=True,
           align=PP_ALIGN.CENTER, fill=PURPLE_DARK)
style_cell(hdr_c.cells[1], 'Бизнес',
           font=HEAD_FONT, size=14, color=WHITE, bold=True,
           align=PP_ALIGN.CENTER, fill=PURPLE_DARK)
style_cell(hdr_c.cells[2], 'VIP',
           font=HEAD_FONT, size=14, color=WHITE, bold=True,
           align=PP_ALIGN.CENTER, fill=PURPLE_DARK)

for ri, (stage, biz, vip) in enumerate(cjm_rows, start=1):
    ctbl.rows[ri].height = Inches(0.78)
    fill = WHITE if ri % 2 == 1 else LAVENDER_LIGHT
    style_cell(ctbl.rows[ri].cells[0], stage,
               font=BODY_FONT, size=12, color=PURPLE_DARK, bold=True,
               align=PP_ALIGN.LEFT, fill=LAVENDER_LIGHT)
    style_cell(ctbl.rows[ri].cells[1], biz,
               font=BODY_FONT, size=11, color=DARK_BODY,
               align=PP_ALIGN.LEFT, fill=fill)
    style_cell(ctbl.rows[ri].cells[2], vip,
               font=BODY_FONT, size=11, color=DARK_BODY,
               align=PP_ALIGN.LEFT, fill=fill)

# Bottom callout
add_rounded_block(s3, Inches(0.7), Inches(6.35),
                  Inches(12.0), Inches(0.6),
                  fill=LAVENDER_BG)
add_text(s3,
         'Граница между тарифами — не функции, а ответ на вопрос: «Один ли я в важной точке — или рядом человек?»',
         Inches(0.7), Inches(6.35), Inches(12.0), Inches(0.6),
         font=BODY_FONT, size=14, color=PURPLE_DARK, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

add_chrome(s3, prs)


# ─── Slide 4: Сообщество ──────────────────────────────────────────────────────
s4 = prs.slides.add_slide(BLANK)

add_text(s4, 'Сообщество как платформа',
         Inches(0.7), Inches(0.5), Inches(11), Inches(0.8),
         font=HEAD_FONT, size=32, color=PURPLE, bold=True)

# Two columns: Сохраняем | Строим
col_y = Inches(1.5)
col_h = Inches(3.6)
col_w = Inches(5.85)

# LEFT column — Сохраняем
add_rounded_block(s4, Inches(0.7), col_y, col_w, col_h, fill=LAVENDER_LIGHT)
add_text(s4, 'Что сохраняем как есть',
         Inches(0.95), col_y + Inches(0.2), col_w - Inches(0.5), Inches(0.4),
         font=HEAD_FONT, size=16, color=PURPLE_DARK, bold=True)

keep_items = [
    '@oqode как публичный медиа-канал',
    '@zerocoders как сердце сообщества (с участием Кирилла)',
    'Нейроклуб как платный продукт (1900/3900 ₽)',
    'Активисты, которые уже сейчас нам помогают',
]

for i, item in enumerate(keep_items):
    y = col_y + Inches(0.85 + i * 0.55)
    # bullet
    b = s4.shapes.add_shape(MSO_SHAPE.OVAL,
                             Inches(0.95), y + Inches(0.13),
                             Inches(0.1), Inches(0.1))
    b.fill.solid()
    b.fill.fore_color.rgb = GREEN
    b.line.fill.background()
    b.shadow.inherit = False
    add_text(s4, item,
             Inches(1.2), y, col_w - Inches(0.6), Inches(0.5),
             font=BODY_FONT, size=12, color=DARK_BODY)

# RIGHT column — Строим
right_x = Inches(7.0)
add_rounded_block(s4, right_x, col_y, col_w, col_h, fill=LAVENDER_BG)
add_text(s4, 'Что строим',
         right_x + Inches(0.25), col_y + Inches(0.2), col_w - Inches(0.5), Inches(0.4),
         font=HEAD_FONT, size=16, color=PURPLE_DARK, bold=True)

build_items = [
    'Платформа сообщества внутри Zerocoder',
    'ИИ-фасилитатор как умный фильтр потока',
    '5 слоёв: микро-круг → ниша → поток → общее → клуб выпускников',
    'Программа Ambassadors (формализация активистов)',
    'Клуб выпускников по уровням тарифов',
    'Нейроклуб в линейке: Базовый / Pro / Inner Circle',
]

for i, item in enumerate(build_items):
    y = col_y + Inches(0.85 + i * 0.45)
    b = s4.shapes.add_shape(MSO_SHAPE.OVAL,
                             right_x + Inches(0.25), y + Inches(0.13),
                             Inches(0.1), Inches(0.1))
    b.fill.solid()
    b.fill.fore_color.rgb = PURPLE
    b.line.fill.background()
    b.shadow.inherit = False
    add_text(s4, item,
             right_x + Inches(0.5), y, col_w - Inches(0.7), Inches(0.45),
             font=BODY_FONT, size=11, color=DARK_BODY)

# Bottom block — student experience
exp_y = Inches(5.3)
exp_h = Inches(1.55)
add_rounded_block(s4, Inches(0.7), exp_y, Inches(12.0), exp_h,
                  fill=WHITE, line=PURPLE)
add_text(s4,
         'Что видит студент:',
         Inches(0.95), exp_y + Inches(0.1), Inches(11), Inches(0.35),
         font=HEAD_FONT, size=13, color=PURPLE_DARK, bold=True)
add_text(s4,
         'Маша открывает платформу — один диалог с ИИ-наставником. Через него прилетает: «Игорь из твоего круга поделился кейсом», '
         '«В твоей нише обсуждают новый алгоритм YouTube», «Аня хочет поговорить про сторителлинг», «Завтра урок про монтаж». '
         'Всё фильтрованное, релевантное, без шума. SLA 15 мин сохраняется при росте базы в 5–10 раз — за счёт ИИ-фасилитатора и Ambassadors.',
         Inches(0.95), exp_y + Inches(0.5), Inches(11.6), Inches(1.0),
         font=BODY_FONT, size=11, color=DARK_BODY)

add_chrome(s4, prs)


# ─── Slide 5: Что это даёт + закрытие ─────────────────────────────────────────
s5 = prs.slides.add_slide(BLANK)

add_text(s5, 'Что это даёт компании',
         Inches(0.7), Inches(0.5), Inches(11), Inches(0.8),
         font=HEAD_FONT, size=32, color=PURPLE, bold=True)

# 5 numbered tezisов
tezisy = [
    ('1', 'Доходимость в 2030',
     'решается не уроками и не куратором, а дизайном внимания'),
    ('2', 'Новая статья выручки — подписка на ИИ-агента',
     'действующая во время и после обучения'),
    ('3', 'Единая платформа сообщества с ИИ-фасилитатором',
     'вместо 20+ разрозненных чатов студент видит один умный поток'),
    ('4', 'ФОТ растёт пропорционально VIP-сегменту',
     'а не базе клиентов'),
    ('5', 'Курс — начало отношений, а не конец',
     'агент студента работает в его задачах ежедневно и увеличивает LTV кратно'),
]

card_y_start = 1.5
card_h = 0.7
gap = 0.1
card_w = 12.0
for i, (num, title, body) in enumerate(tezisy):
    y = Inches(card_y_start + i * (card_h + gap))
    # number circle
    circle = s5.shapes.add_shape(MSO_SHAPE.OVAL,
                                  Inches(0.7), y + Inches(0.12),
                                  Inches(0.45), Inches(0.45))
    circle.fill.solid()
    circle.fill.fore_color.rgb = PURPLE
    circle.line.fill.background()
    circle.shadow.inherit = False
    add_text(s5, num,
             Inches(0.7), y + Inches(0.12), Inches(0.45), Inches(0.45),
             font=HEAD_FONT, size=18, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    # title + body, two runs
    tx = s5.shapes.add_textbox(Inches(1.4), y, Inches(11.3), Inches(0.7))
    tf = tx.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r1 = p.add_run()
    set_run(r1, title + ' — ',
            font=HEAD_FONT, size=14, color=PURPLE_DARK, bold=True)
    r2 = p.add_run()
    set_run(r2, body,
            font=BODY_FONT, size=13, color=DARK_BODY)

# Finale block
fin_y = Inches(5.3)
fin_h = Inches(1.65)
add_rounded_block(s5, Inches(0.7), fin_y, Inches(12.0), fin_h,
                  fill=LAVENDER_BG)
add_text(s5,
         'К 2030 студент Zerocoder уходит не с дипломом.',
         Inches(0.95), fin_y + Inches(0.15), Inches(11.6), Inches(0.45),
         font=HEAD_FONT, size=16, color=PURPLE_DARK, bold=True,
         align=PP_ALIGN.CENTER)
add_text(s5,
         'Он уходит с профессией, рабочим ИИ-инструментом, сетью контактов\nи пожизненной связью с университетом.',
         Inches(0.95), fin_y + Inches(0.6), Inches(11.6), Inches(0.65),
         font=BODY_FONT, size=15, color=DARK_BODY,
         align=PP_ALIGN.CENTER)
add_text(s5,
         'Это новая форма образования. И сопровождение — её сердце.',
         Inches(0.95), fin_y + Inches(1.2), Inches(11.6), Inches(0.4),
         font=HEAD_FONT, size=14, color=GREEN, bold=True,
         align=PP_ALIGN.CENTER)

add_chrome(s5, prs)


# Save
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUTPUT))
print(f'Saved: {OUTPUT}')
