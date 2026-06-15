"""
Анализ удовлетворённости студентов по урокам Zerocoder.
Источник: data/GC-Reviews/2026-06-09-lesson-feedback-raw.csv
Справочник курсов: data/courses-catalog.csv
Выход: reports/YYYY-MM-DD-lesson-feedback-dashboard.html

Метрика «Оценка» — взвешенный балл по 5-балльной шкале:
   Понравился = 5, Неплохо = 3, Не понравился = 1
"""

import html
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "GC-Reviews" / "2026-06-09-lesson-feedback-raw.csv"
CATALOG = ROOT / "data" / "courses-catalog.csv"
OUT = ROOT / "reports" / f"{date.today().isoformat()}-lesson-feedback-dashboard.html"

POS = "Понравился, все было понятно"
NEU = "Неплохо, но не все получилось/не все понятно"
NEG = "Не понравился"
GRADE_COLOR = {POS: "#22c55e", NEU: "#f59e0b", NEG: "#ef4444"}

MIN_COURSE = 100
MIN_MODULE = 20
MIN_LESSON = 10

# ── СПРАВОЧНИК ───────────────────────────────────────────────────
catalog = pd.read_csv(CATALOG, dtype=str, keep_default_na=False)
catalog["name"] = catalog["name"].str.strip()

CATEGORY_ORDER = [
    "Профессии",
    "Программы по нейросетям",
    "Инструментальные программы",
    "Премиальные программы",
    "Для детей",
    "Прочее",
]

# ── ПРАВИЛА МАТЧИНГА ─────────────────────────────────────────────
COURSES = [
    ("Вайб-кодинг с OpenClaw",                        "Программы по нейросетям", ["openclaw", "опенклоу"]),
    ("Вайб-кодинг на Claude Code",                    "Программы по нейросетям", ["claude code", "claudecode", "клод код"]),
    ("Вайб-кодинг и автономные агенты",               "Программы по нейросетям", ["vibe-coding", "vibe coding", "автономн"]),
    ("Вайб-кодер",                                    "Профессии",                ["вайб-кодер", "вайб кодер", "вайб - кодер", "вайб- кодер", "нейро кодинг"]),
    ("Перплексити: от новичка до Pro",                "Программы по нейросетям", ["perplexity", "перплекс", "preplex", "perplexiti"]),
    ("Промпт-инжиниринг",                             "Профессии",                ["промпт", "промт"]),
    ("Нейроденьги",                                   "Программы по нейросетям", ["нейродень"]),
    ("Нейросети для юристов",                         "Программы по нейросетям", ["юрист", "юриспруд"]),
    ("Курс по ИИ-экосистеме Google",                  "Программы по нейросетям", ["google", "gemini", "ai-экосистем", "ai экосистем", "экосистема google", "гугл"]),
    ("Автоматизатор: от 0 до Pro",                    "Профессии",                ["автоматизатор"]),
    ("Автоматизация на n8n",                          "Инструментальные программы", ["n8n", "н8н", "no-code", "no code", "ноу-код"]),
    ("Разработчик чат-ботов под ключ",                "Профессии",                ["чат-бот", "чат бот", "чатбот"]),
    ("Визуальный контент с ИИ",                       "Программы по нейросетям", ["визуальн контент", "визуальный контент"]),
    ("Нейросети без границ с российскими инструментами", "Программы по нейросетям", ["без границ"]),
    ("ИИ для работы с таблицами",                     "Программы по нейросетям", ["таблиц"]),
    ("Программист на Python с ChatGPT",               "Прочее",                   ["python", "питон"]),
    ("Презентации с ИИ",                              "Программы по нейросетям", ["презентац"]),
    ("Вайб-маркетинг",                                "Программы по нейросетям", ["вайб-маркетинг", "вайб маркетинг", "вайбмаркетинг"]),
    ("Аналитик данных с нуля",                        "Профессии",                ["аналитик данных", "аналитик данные"]),
    ("ИИ-экосистема Яндекса",                         "Программы по нейросетям", ["яндекс"]),
    ("Нейросети для здоровья",                        "Программы по нейросетям", ["здоров"]),
    ("Нейросети для преподавателя",                   "Программы по нейросетям", ["преподават", "учител"]),
    ("ГигаЧат",                                       "Программы по нейросетям", ["гигачат", "гига чат", "гига-чат"]),
    ("Цифровой старт",                                "Программы по нейросетям", ["цифровой старт", "цифр старт"]),
    ("Веб-дизайнер",                                  "Профессии",                ["веб-дизайнер", "веб дизайнер"]),
    ("Нейросети ПРО",                                 "Программы по нейросетям", ["нейросети pro", "нейросети про", "нейросеть pro"]),
    ("Нейросети для бухгалтеров и финансистов",       "Программы по нейросетям", ["бухгалтер", "финансист"]),
    ("Нейросети для жизни",                           "Программы по нейросетям", ["для жизни"]),
    ("ИИ для инвестиций",                             "Программы по нейросетям", ["инвестиц"]),
    ("IT-стартап без границ",                         "Прочее",                   ["it-стартап", "it стартап"]),
    ("1С-разработчик",                                "Профессии",                ["1с"]),
    ("Tilda",                                         "Прочее",                   ["tilda", "тильда"]),
    ("Figma",                                         "Прочее",                   ["figma", "фигма"]),
    ("WordPress",                                     "Инструментальные программы", ["wordpress", "вордпресс"]),
    ("Китайские нейросети",                           "Программы по нейросетям", ["китайск"]),
    ("FlutterFlow",                                   "Прочее",                   ["flutterflow"]),
    ("Мобильный разработчик на Flutter",              "Прочее",                   ["flutter"]),
    ("Webflow",                                       "Инструментальные программы", ["webflow"]),
    ("Своя ИИ-студия",                                "Премиальные программы",    ["ии студия", "ai студия", "ai студ", "премиальн"]),
    ("ИИ-копирайтинг",                                "Программы по нейросетям", ["копирайтер", "копирайтинг"]),
    ("UX/UI",                                         "Прочее",                   ["ux/ui", "ux ui"]),
    ("Нейросети для журналистов",                     "Программы по нейросетям", ["журналист", "жкрналист", "пишущих"]),
    ("Нейросети от принципов к практике",             "Программы по нейросетям", ["принципов к практике"]),
    ("Подработка с ИИ",                               "Программы по нейросетям", ["подработк"]),
    ("Автоматизация на n8n",                          "Инструментальные программы", ["автоматизация"]),
]


def canonicalize(raw: str):
    if not raw:
        return None
    s = raw.lower().replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    version = "база"
    if "(индивидуал" in s:
        version = "индивидуальная"
    m = re.search(r"\b([23])\.0\b", s)
    if m:
        version = f"{m.group(1)}.0"
    if len(s) < 4:
        return None
    if re.fullmatch(r"[0-9\s\.\-]+", s):
        return None
    if re.fullmatch(r"[a-zа-я]{1,5}\s*[0-9]{1,3}", s):
        return None
    if s.strip() in {"нейросети", "азы", "тест", "проба"}:
        return None
    for canonical, category, kws in COURSES:
        for kw in kws:
            if kw in s:
                return (canonical, category, version)
    return None


def lesson_sort_key(name: str):
    """Сортируем уроки по коду в начале: NLw01 → ('nlw', 1)."""
    m = re.match(r"\s*([A-Za-zА-Яа-я]+)(\d+)", name)
    if m:
        return (m.group(1).lower(), int(m.group(2)), name.lower())
    m2 = re.match(r"\s*(\d+)", name)
    if m2:
        return ("", int(m2.group(1)), name.lower())
    return ("zzz", 9999, name.lower())


def module_sort_key(name: str):
    """Модули по порядку прохождения: вводные (-1), потом «Модуль N», прочее в конец."""
    s = name.lower()
    if "вводн" in s or "предобуч" in s or "введение" in s or s.startswith("основы"):
        # явный «модуль 0» = вводный, ставим до -1
        m0 = re.search(r"модул[ьея]\s*(\d+)", s)
        if m0 and int(m0.group(1)) == 0:
            return (-2, s)
        return (-1, s)
    m = re.search(r"модул[ьея]\s*(\d+)", s)
    if m:
        return (int(m.group(1)), s)
    m2 = re.search(r"\b(\d+)\b", s)
    if m2:
        return (int(m2.group(1)), s)
    return (999, s)


# ── ЗАГРУЗКА ─────────────────────────────────────────────────────
df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
df.columns = [c.strip() for c in df.columns]
df["Grade"] = df["Grade"].str.strip()
df = df[df["Grade"].isin({POS, NEU, NEG})].copy()

mapped = df["Course"].fillna("").map(canonicalize)
df["course_canon"] = mapped.map(lambda x: x[0] if x else None)
df["course_cat"] = mapped.map(lambda x: x[1] if x else None)
df["course_version"] = mapped.map(lambda x: x[2] if x else None)
df = df[df["course_canon"].notna()].copy()

df["Modul"] = df["Modul"].fillna("").str.strip().replace("", "(модуль не указан)")
df["Lesson"] = df["Lesson"].fillna("").str.strip().replace("", "(урок не указан)")
df["Comment"] = df["Comment"].fillna("").str.strip()

total = len(df)
pos_total = (df["Grade"] == POS).sum()
neu_total = (df["Grade"] == NEU).sum()
neg_total = (df["Grade"] == NEG).sum()


def esc(s):
    return html.escape(str(s) if s is not None else "")


def grade_stats(frame):
    n = len(frame)
    p = (frame["Grade"] == POS).sum()
    u = (frame["Grade"] == NEU).sum()
    g = (frame["Grade"] == NEG).sum()
    score = (p * 5 + u * 3 + g * 1) / n if n else 0
    return {"total": n, "pos": p, "neu": u, "neg": g, "score": score}


def score_color(s):
    if s >= 4.7:
        return "#22c55e"
    if s >= 4.5:
        return "#84cc16"
    if s >= 4.0:
        return "#f59e0b"
    return "#ef4444"


def kpi_bar(stats, compact=False):
    n = stats["total"] or 1
    pw, uw, gw = stats["pos"] / n * 100, stats["neu"] / n * 100, stats["neg"] / n * 100
    cls = "stack" + (" sm" if compact else "")
    return f"""<div class="{cls}">
      <span style="width:{pw:.2f}%;background:{GRADE_COLOR[POS]}" title="Понравился: {stats['pos']}"></span>
      <span style="width:{uw:.2f}%;background:{GRADE_COLOR[NEU]}" title="Неплохо: {stats['neu']}"></span>
      <span style="width:{gw:.2f}%;background:{GRADE_COLOR[NEG]}" title="Не понравился: {stats['neg']}"></span>
    </div>"""


def course_kpi_block(stats):
    n = stats["total"]
    return f"""<div class="course-kpi">
      <div class="ckpi"><span class="ckpi-v" style="color:{GRADE_COLOR[POS]}">{stats['pos']:,}</span>
        <span class="ckpi-l">Понравился · {stats['pos']/n*100:.1f}%</span></div>
      <div class="ckpi"><span class="ckpi-v" style="color:{GRADE_COLOR[NEU]}">{stats['neu']:,}</span>
        <span class="ckpi-l">Неплохо · {stats['neu']/n*100:.1f}%</span></div>
      <div class="ckpi"><span class="ckpi-v" style="color:{GRADE_COLOR[NEG]}">{stats['neg']:,}</span>
        <span class="ckpi-l">Не понравился · {stats['neg']/n*100:.1f}%</span></div>
      <div class="ckpi"><span class="ckpi-v">{n:,}</span><span class="ckpi-l">Всего оценок</span></div>
    </div>"""


def comments_list(frame, limit=20):
    if frame.empty:
        return ""
    rows = []
    for _, r in frame.head(limit).iterrows():
        rows.append(f'<li><span class="cmt-meta">{esc(r["Lesson"])}</span> — {esc(r["Comment"])}</li>')
    extra = f'<p class="more">…и ещё {len(frame) - limit} комментариев</p>' if len(frame) > limit else ""
    return f'<ul class="cmt-list">{"".join(rows)}</ul>{extra}'


def lesson_table(lessons_df, sort_mode="seq"):
    """sort_mode: 'seq' — по коду урока, 'score' — по оценке снизу."""
    rows = []
    for lesson, sub in lessons_df.groupby("Lesson", sort=False):
        st = grade_stats(sub)
        if st["total"] < MIN_LESSON:
            continue
        rows.append((lesson, st))
    if sort_mode == "seq":
        rows.sort(key=lambda x: lesson_sort_key(x[0]))
    else:
        rows.sort(key=lambda x: x[1]["score"])
    if not rows:
        return f"<p class='muted'>Нет уроков с ≥ {MIN_LESSON} ответами.</p>"
    out = ['<table class="lesson-tbl"><thead><tr><th>Урок</th><th>Ответов</th><th>Оценка</th><th>Распределение</th></tr></thead><tbody>']
    for lesson, st in rows:
        cls = "row-bad" if st["score"] < 4.0 else ("row-warn" if st["score"] < 4.5 else "")
        out.append(f"""<tr class="{cls}">
          <td class="lbl">{esc(lesson)}</td>
          <td class="num">{st['total']}</td>
          <td class="num"><b style="color:{score_color(st['score'])}">{st['score']:.2f}</b></td>
          <td class="bar">{kpi_bar(st, compact=True)}</td>
        </tr>""")
    out.append("</tbody></table>")
    return "".join(out)


# ── СБОРКА КУРСОВ ────────────────────────────────────────────────
course_groups = sorted(df.groupby("course_canon"), key=lambda x: -len(x[1]))
courses_by_cat = {}
toc_rows = []
course_best_worst = []  # для нижних блоков

for course, cdf in course_groups:
    if len(cdf) < MIN_COURSE:
        continue
    cat = cdf["course_cat"].iloc[0] or "Прочее"
    cstats = grade_stats(cdf)

    # версии
    versions_html = ""
    vgroups = cdf.groupby("course_version")
    if vgroups.ngroups > 1:
        vrows = []
        for ver, vdf in sorted(vgroups, key=lambda x: -len(x[1])):
            vst = grade_stats(vdf)
            vrows.append(f"""<tr>
              <td class="lbl">{esc(ver)}</td>
              <td class="num">{vst['total']:,}</td>
              <td class="num"><b style="color:{score_color(vst['score'])}">{vst['score']:.2f}</b></td>
              <td class="num" style="color:{GRADE_COLOR[NEG]}">{vst['neg']} ({vst['neg']/vst['total']*100:.1f}%)</td>
              <td class="bar">{kpi_bar(vst, compact=True)}</td>
            </tr>""")
        versions_html = f"""<div class="subsection">
          <h3>Версии курса</h3>
          <table><thead><tr>
            <th>Версия</th><th>Ответов</th><th>Оценка</th><th>Не понравился</th><th>Распределение</th>
          </tr></thead><tbody>{''.join(vrows)}</tbody></table>
        </div>"""

    # модули
    module_blocks = []
    course_lesson_stats = []  # все уроки курса для глобальных блоков

    for modul, mdf in sorted(cdf.groupby("Modul"), key=lambda x: module_sort_key(x[0])):
        if len(mdf) < MIN_MODULE:
            continue
        mst = grade_stats(mdf)

        lesson_stats = []
        for lesson, ldf in mdf.groupby("Lesson"):
            ls = grade_stats(ldf)
            if ls["total"] < MIN_LESSON:
                continue
            lesson_stats.append((lesson, ls))
            course_lesson_stats.append((modul, lesson, ls))

        # худшие/лучшие — только если уроков достаточно, чтобы не пересекались
        n_lessons = len(lesson_stats)
        best_worst_html = ""
        if n_lessons >= 7:
            by_score = sorted(lesson_stats, key=lambda x: x[1]["score"])
            worst3 = by_score[:3]
            best3 = sorted(by_score[-3:], key=lambda x: -x[1]["score"])
            worst_html = "".join(
                f'<li><b>{esc(l)}</b> — оценка {s["score"]:.2f}, {s["total"]} отв., «не понравился» {s["neg"]}</li>'
                for l, s in worst3
            )
            best_html = "".join(
                f'<li><b>{esc(l)}</b> — оценка {s["score"]:.2f}, {s["total"]} отв.</li>'
                for l, s in best3
            )
            best_worst_html = f"""<div class="best-worst">
              <div><h4>Худшие уроки модуля</h4><ol>{worst_html}</ol></div>
              <div><h4>Лучшие уроки модуля</h4><ol>{best_html}</ol></div>
            </div>"""

        neg_cm = mdf[(mdf["Grade"] == NEG) & (mdf["Comment"].str.len() > 5)]
        neu_cm = mdf[(mdf["Grade"] == NEU) & (mdf["Comment"].str.len() > 5)]
        neg_block = f"""<details class="cmt-det"><summary>Негативные комментарии модуля ({len(neg_cm)})</summary>{comments_list(neg_cm, limit=30)}</details>""" if len(neg_cm) else ""
        neu_block = f"""<details class="cmt-det"><summary>Сигнальные «неплохо» ({len(neu_cm)})</summary>{comments_list(neu_cm, limit=30)}</details>""" if len(neu_cm) else ""

        full_table = lesson_table(mdf, sort_mode="seq")

        module_blocks.append(f"""<details class="module">
          <summary>
            <span class="m-name">{esc(modul)}</span>
            <span class="m-meta">{mst['total']:,} отв. · оценка {mst['score']:.2f} · нег. {mst['neg']}</span>
            <span class="m-bar">{kpi_bar(mst, compact=True)}</span>
          </summary>
          <div class="module-body">
            {best_worst_html}
            <div class="subsection">
              <h4>Все уроки модуля (в порядке прохождения)</h4>
              {full_table}
            </div>
            {neg_block}
            {neu_block}
          </div>
        </details>""")

    modules_html = "\n".join(module_blocks) if module_blocks else "<p class='muted'>Нет модулей с достаточным числом ответов.</p>"

    anchor = re.sub(r"[^a-zа-я0-9]+", "-", course.lower()).strip("-")
    open_attr = " open" if len(cdf) >= 5000 else ""
    block = f"""<details class="course" id="c-{anchor}"{open_attr}>
      <summary class="course-head">
        <h2>{esc(course)}</h2>
        <span class="course-meta">{cstats['total']:,} оценок · оценка {cstats['score']:.2f}</span>
      </summary>
      <div class="course-body">
        {course_kpi_block(cstats)}
        {versions_html}
        <div class="subsection">
          <h3>Модули</h3>
          {modules_html}
        </div>
      </div>
    </details>"""
    courses_by_cat.setdefault(cat, []).append(block)

    toc_rows.append(f"""<tr>
      <td class="lbl"><a href="#c-{anchor}">{esc(course)}</a></td>
      <td class="num">{cstats['total']:,}</td>
      <td class="num" style="color:{GRADE_COLOR[POS]}">{cstats['pos']:,} ({cstats['pos']/cstats['total']*100:.1f}%)</td>
      <td class="num" style="color:{GRADE_COLOR[NEU]}">{cstats['neu']:,} ({cstats['neu']/cstats['total']*100:.1f}%)</td>
      <td class="num" style="color:{GRADE_COLOR[NEG]}">{cstats['neg']} ({cstats['neg']/cstats['total']*100:.1f}%)</td>
      <td class="bar">{kpi_bar(cstats, compact=True)}</td>
    </tr>""")

    # топ худших/лучших уроков для нижнего блока — по этому курсу
    if course_lesson_stats:
        by_score = sorted(course_lesson_stats, key=lambda x: x[2]["score"])
        worst_c = by_score[:3]
        best_c = sorted(by_score, key=lambda x: -x[2]["score"])[:3]
        # избегаем пересечений
        worst_set = {(m, l) for m, l, _ in worst_c}
        best_c = [x for x in best_c if (x[0], x[1]) not in worst_set][:3]
        course_best_worst.append((course, worst_c, best_c))


# ── СЕКЦИИ ПО КАТЕГОРИЯМ ─────────────────────────────────────────
category_sections = []
for cat in CATEGORY_ORDER:
    blocks = courses_by_cat.get(cat, [])
    if not blocks:
        continue
    category_sections.append(f"""<section class="category">
      <h2 class="cat-title">{esc(cat)} <span class="cat-meta">· {len(blocks)} курсов</span></h2>
      {''.join(blocks)}
    </section>""")


# ── НИЖНИЕ БЛОКИ: ТОП ПО КУРСАМ ──────────────────────────────────
def course_top_block(title, picker):
    """picker(course_data) → list of (modul, lesson, stats)"""
    rows_html = []
    for course, worst_c, best_c in course_best_worst:
        items = picker(worst_c, best_c)
        if not items:
            continue
        item_rows = "".join(
            f"""<tr>
              <td class="lbl-sm">{esc(modul)}</td>
              <td class="lbl">{esc(lesson)}</td>
              <td class="num">{s['total']}</td>
              <td class="num"><b style="color:{score_color(s['score'])}">{s['score']:.2f}</b></td>
              <td class="num" style="color:{GRADE_COLOR[NEG]}">{s['neg']}</td>
              <td class="bar">{kpi_bar(s, compact=True)}</td>
            </tr>"""
            for modul, lesson, s in items
        )
        rows_html.append(f"""<div class="course-top">
          <h3>{esc(course)}</h3>
          <table>
            <thead><tr><th>Модуль</th><th>Урок</th><th>Отв.</th><th>Оценка</th><th>Нег.</th><th>Распределение</th></tr></thead>
            <tbody>{item_rows}</tbody>
          </table>
        </div>""")
    return f"""<section class="card">
      <h2>{esc(title)}</h2>
      {''.join(rows_html)}
    </section>"""


worst_section = course_top_block("Худшие уроки — по каждому курсу (топ-3)", lambda w, b: w)
best_section = course_top_block("Лучшие уроки — по каждому курсу (топ-3)", lambda w, b: b)

total_courses = sum(len(v) for v in courses_by_cat.values())

# ── HTML ─────────────────────────────────────────────────────────
TPL = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<title>Удовлетворённость по урокам — Zerocoder</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin:0; padding:32px;
         background:#f5f6fa; color:#1f2937; }}
  h1 {{ margin:0 0 4px; }}
  h2 {{ margin:0; font-size:20px; color:#111827; }}
  h3 {{ margin:18px 0 10px; font-size:14px; color:#374151;
        text-transform:uppercase; letter-spacing:.4px; font-weight:600; }}
  h4 {{ margin:8px 0 6px; font-size:12px; color:#6b7280; text-transform:uppercase;
        letter-spacing:.3px; font-weight:600; }}
  .sub {{ color:#6b7280; margin:-8px 0 16px; font-size:14px; }}
  .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:16px; margin:24px 0; }}
  .kpi {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  .kpi .v {{ font-size:32px; font-weight:700; }}
  .kpi .l {{ color:#6b7280; font-size:13px; margin-top:4px; }}
  .card {{ background:#fff; border-radius:12px; padding:24px; margin-bottom:20px;
           box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  table {{ width:100%; border-collapse: collapse; font-size:14px; }}
  th, td {{ padding:8px 10px; border-bottom:1px solid #f1f5f9; vertical-align:middle; text-align:left; }}
  th {{ color:#6b7280; font-weight:500; font-size:12px; text-transform:uppercase; letter-spacing:.4px; }}
  .lbl {{ max-width:520px; }}
  .lbl-sm {{ font-size:13px; color:#374151; max-width:240px; }}
  .num {{ text-align:right; white-space:nowrap; width:110px; }}
  .bar {{ width:180px; }}
  .stack {{ display:flex; height:14px; border-radius:7px; overflow:hidden; background:#e5e7eb; }}
  .stack.sm {{ height:10px; }}
  .stack span {{ display:block; height:100%; }}
  .legend {{ display:flex; gap:16px; font-size:13px; color:#6b7280; margin-bottom:8px; }}
  .legend span::before {{ content:""; display:inline-block; width:10px; height:10px;
                          border-radius:2px; margin-right:6px; vertical-align:middle; }}
  .legend .pos::before {{ background:{GRADE_COLOR[POS]}; }}
  .legend .neu::before {{ background:{GRADE_COLOR[NEU]}; }}
  .legend .neg::before {{ background:{GRADE_COLOR[NEG]}; }}
  .scale-hint {{ font-size:12px; color:#6b7280; margin-top:4px; }}

  .category {{ margin:32px 0 8px; }}
  .cat-title {{ font-size:22px; font-weight:700; color:#111827; margin:0 0 12px;
                padding-bottom:8px; border-bottom:2px solid #e5e7eb; }}
  .cat-meta {{ color:#9ca3af; font-size:14px; font-weight:400; }}

  details.course {{ background:#fff; border-radius:12px; margin-bottom:12px;
                    box-shadow:0 1px 3px rgba(0,0,0,.05); overflow:hidden; }}
  details.course > summary {{ list-style:none; cursor:pointer; padding:16px 24px;
                              display:flex; justify-content:space-between; align-items:center; }}
  details.course[open] > summary {{ border-bottom:1px solid #f1f5f9; }}
  details.course > summary::-webkit-details-marker {{ display:none; }}
  details.course > summary::before {{ content:"▸"; color:#9ca3af; margin-right:10px;
                                       transition:transform .15s; display:inline-block; }}
  details.course[open] > summary::before {{ transform:rotate(90deg); }}
  .course-head h2 {{ display:inline; }}
  .course-meta {{ color:#6b7280; font-size:13px; }}
  .course-body {{ padding:0 24px 20px; }}

  .course-kpi {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }}
  .ckpi {{ background:#f9fafb; padding:14px 16px; border-radius:8px;
          display:flex; flex-direction:column; gap:2px; }}
  .ckpi-v {{ font-size:22px; font-weight:700; }}
  .ckpi-l {{ color:#6b7280; font-size:12px; }}

  details.module {{ background:#fafbfc; border:1px solid #eef0f3; border-radius:8px;
                    margin-bottom:8px; }}
  details.module > summary {{ list-style:none; cursor:pointer; padding:10px 14px;
                              display:grid; grid-template-columns:1fr 260px 180px; gap:12px;
                              align-items:center; }}
  details.module > summary::-webkit-details-marker {{ display:none; }}
  details.module > summary::before {{ content:"▸"; color:#9ca3af; margin-right:6px;
                                      display:inline-block; transition:transform .15s; }}
  details.module[open] > summary::before {{ transform:rotate(90deg); }}
  .m-name {{ font-weight:600; color:#111827; font-size:14px; }}
  .m-meta {{ color:#6b7280; font-size:12px; text-align:right; }}
  .module-body {{ padding:0 14px 14px; }}

  .best-worst {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:10px 0; }}
  .best-worst ol {{ margin:0; padding-left:18px; font-size:13px; }}
  .best-worst li {{ margin:4px 0; }}

  .subsection {{ margin-top:12px; }}
  .row-bad {{ background:#fef2f2; }}
  .row-warn {{ background:#fffbeb; }}

  .course-top {{ margin:18px 0; }}
  .course-top h3 {{ font-size:14px; color:#111827; text-transform:none; letter-spacing:0;
                    font-weight:600; margin:0 0 8px; }}

  details.cmt-det {{ margin-top:10px; background:#fff; border:1px solid #eef0f3;
                     border-radius:6px; padding:8px 12px; }}
  details.cmt-det summary {{ cursor:pointer; font-size:13px; color:#374151; font-weight:500; }}
  .cmt-list {{ margin:10px 0 6px; padding-left:18px; font-size:13px; }}
  .cmt-list li {{ margin:6px 0; line-height:1.4; }}
  .cmt-meta {{ color:#6b7280; font-size:12px; }}
  .more {{ color:#9ca3af; font-size:12px; margin:6px 0 0; }}
  .muted {{ color:#9ca3af; font-size:13px; }}
  .footer {{ color:#9ca3af; font-size:12px; margin-top:24px; }}
  a {{ color:#2563eb; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
</style></head>
<body>

<h1>Удовлетворённость студентов по урокам</h1>
<p class="sub">Источник: GetCourse · выгрузка от 2026-06-09 · {total:,} валидных оценок · {total_courses} курсов</p>

<div class="legend">
  <span class="pos">Понравился</span>
  <span class="neu">Неплохо, но не всё понятно</span>
  <span class="neg">Не понравился</span>
</div>
<p class="scale-hint">Оценка — взвешенный балл по 5-балльной шкале: «Понравился» = 5, «Неплохо» = 3, «Не понравился» = 1.</p>

<div class="grid">
  <div class="kpi"><div class="v">{total:,}</div><div class="l">Всего оценок</div></div>
  <div class="kpi"><div class="v" style="color:{GRADE_COLOR[POS]}">{pos_total:,}</div><div class="l">Понравился · {pos_total/total*100:.1f}%</div></div>
  <div class="kpi"><div class="v" style="color:{GRADE_COLOR[NEU]}">{neu_total:,}</div><div class="l">Неплохо · {neu_total/total*100:.1f}%</div></div>
  <div class="kpi"><div class="v" style="color:{GRADE_COLOR[NEG]}">{neg_total:,}</div><div class="l">Не понравился · {neg_total/total*100:.2f}%</div></div>
</div>

<section class="card">
  <h2>Сводка по курсам</h2>
  <p class="sub">Клик по названию — перейти к подробному блоку.</p>
  <table>
    <thead><tr>
      <th>Курс</th><th>Ответов</th><th>Понравился</th><th>Неплохо</th><th>Не понравился</th><th>Распределение</th>
    </tr></thead>
    <tbody>{''.join(toc_rows)}</tbody>
  </table>
</section>

{''.join(category_sections)}

{worst_section}

{best_section}

<p class="footer">Сгенерировано {date.today().isoformat()} · scripts/analyze-lesson-feedback.py</p>

</body></html>"""

OUT.write_text(TPL, encoding="utf-8")
print(f"OK -> {OUT}")
print(f"Total: {total} | avg score: {(pos_total*5+neu_total*3+neg_total*1)/total:.2f} | Neg: {neg_total} ({neg_total/total*100:.2f}%)")
print(f"Courses shown: {total_courses}")
