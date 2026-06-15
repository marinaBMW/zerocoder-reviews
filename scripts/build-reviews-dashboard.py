"""
Рендерит главный дашборд отзывов:
  reports/{YYYY-MM-DD}-reviews-dashboard.html
+ плоские CSV в reports/sheets/ под импорт в Google Sheets.

Дизайн повторяет reports/2026-05-15-analytics-dashboard.html
(тёмная тема, Chart.js 4.4.0).
"""

import csv
import json
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA = PROJECT_ROOT / "tmp" / "dashboard-data.json"
REPORTS = PROJECT_ROOT / "reports"
SHEETS = REPORTS / "sheets"

SOURCE_LABEL = {
    "otzovik":    "Отзовик",
    "gc":         "GetCourse (внутр.)",
    "tutortop":   "TutorTop",
    "okursah":    "okursah.ru",
    "skill2go":   "skill2go",
    "2gis":       "2ГИС",
    "pgdv":       "pgdv.ru",
    "yandex":     "Яндекс Карты",
    "irecommend": "iRecommend",
    "kurshub":    "KursHub",
    "google":     "Google Maps",
}

CAT_LABEL = {
    "why_chosen":         "Почему выбирают",
    "objections":         "Возражения",
    "strengths":          "Что зашло",
    "weaknesses":         "Что не зашло",
    "perplexity_special": "Перплексити (главная боль)",
    "theme_sales":        "Тема: Продажи",
    "theme_price":        "Тема: Цена",
    "landing_quotes":     "Цитаты для лендинга",
}


def fmt(v, kind="num"):
    if v is None:
        return "—"
    if kind == "rating":
        return f"{v:.2f}★"
    if kind == "pct":
        return f"{v:.1f}%"
    return f"{v}"


def write_sheets_csvs(data):
    SHEETS.mkdir(parents=True, exist_ok=True)
    # by-source
    with open(SHEETS / "by-source.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Площадка", "Кол-во отзывов", "Средний рейтинг", "% с ответом"])
        for s in data["by_source"]:
            w.writerow([
                SOURCE_LABEL.get(s["source"], s["source"]),
                s["count"],
                s["avg_rating_5"] if s["avg_rating_5"] is not None else "",
                s["with_reply_pct"],
            ])
    # courses
    for key, fname in [("courses_top", "courses-top.csv"),
                       ("courses_bottom", "courses-bottom.csv")]:
        with open(SHEETS / fname, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Курс", "Кол-во отзывов", "Оценка", "Источник оценки"])
            for c in data[key]:
                w.writerow([c["course"], c["count"], c["score"], c["score_source"]])
    # themes
    with open(SHEETS / "themes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Тема", "Упоминаний", "Положит.", "Нейтр.", "Отриц.", "% негатива"])
        for t in data["themes"]:
            w.writerow([t["theme"], t["mentions"], t["pos"], t["neu"], t["neg"], t["neg_pct"]])
    # monthly
    with open(SHEETS / "monthly.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Месяц", "Кол-во отзывов", "Средний рейтинг"])
        for m in data["monthly"]:
            w.writerow([m["month"], m["count"],
                        m["avg_rating_5"] if m["avg_rating_5"] is not None else ""])
    # insights (если есть)
    insights = data.get("insights") or {}
    if insights:
        with open(SHEETS / "insights.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Категория", "Тезис", "Цитата", "Площадка", "Курс"])
            for key, items in insights.items():
                # пропускаем скалярные поля (например generated_at)
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    w.writerow([
                        CAT_LABEL.get(key, key),
                        it.get("text", ""),
                        it.get("quote", ""),
                        it.get("source", ""),
                        it.get("course", ""),
                    ])


def render_summary(d):
    s = d["summary"]
    return f"""
<div class="section">
  <div class="section-title">Сводные показатели</div>
  <div class="grid-4">
    <div class="card">
      <div class="card-title">Всего отзывов</div>
      <div class="card-value green">{s['total']}</div>
      <div class="card-sub">{s['sources']} площадок (включая GetCourse)</div>
    </div>
    <div class="card">
      <div class="card-title">Средний рейтинг (внешние)</div>
      <div class="card-value yellow">{fmt(s['avg_rating_5_global'], 'rating')}</div>
      <div class="card-sub">по площадкам, где есть оценки</div>
    </div>
    <div class="card">
      <div class="card-title">С ответом представителя</div>
      <div class="card-value purple">{s['with_reply']}</div>
      <div class="card-sub">{fmt(s['with_reply_pct'], 'pct')} от всех отзывов</div>
    </div>
    <div class="card">
      <div class="card-title">Снимок данных</div>
      <div class="card-value">{d['generated_at']}</div>
      <div class="card-sub">обновляется скриптами</div>
    </div>
  </div>
</div>
"""


def render_sources(d):
    rows = "".join(
        f"<tr><td>{SOURCE_LABEL.get(s['source'], s['source'])}</td>"
        f"<td>{s['count']}</td>"
        f"<td>{fmt(s['avg_rating_5'], 'rating')}</td>"
        f"<td>{fmt(s['with_reply_pct'], 'pct')}</td></tr>"
        for s in d["by_source"]
    )
    return f"""
<div class="section">
  <div class="section-title">Рейтинг по площадкам</div>
  <div class="card" style="margin-bottom:16px;">
    <div class="card-title">Контраст: «платные» каталоги vs карточные сервисы</div>
    <div class="card-sub" style="font-size:13px;line-height:1.6;">
      На каталогах (TutorTop, okursah, skill2go, KursHub) средний рейтинг
      <b class="green">4.6+</b> — там модерация и фильтрация.
      На карточных сервисах (Яндекс Карты, iRecommend, 2ГИС) средний
      <b class="red">3.3–4.3</b> — там органика и эмоции.
    </div>
  </div>
  <div class="grid-2">
    <div class="card">
      <div class="card-title">Количество отзывов и средняя оценка</div>
      <div class="chart-wrap-lg"><canvas id="chartSources"></canvas></div>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>Площадка</th><th>Отзывов</th><th>Ср. рейтинг</th><th>С ответом</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</div>
"""


def render_courses(d):
    def table(items, title, color_class, highlight_course=None):
        rows_html = []
        for c in items:
            is_hl = highlight_course and highlight_course.lower() in c["course"].lower()
            row_style = ' style="background: rgba(248,113,113,0.12); border-left: 3px solid #F87171;"' if is_hl else ""
            badge = ' <span style="color:#F87171;font-size:11px;font-weight:700;">⚠ ГЛАВНАЯ БОЛЬ</span>' if is_hl else ""
            rows_html.append(
                f"<tr{row_style}><td>{c['course']}{badge}</td>"
                f"<td>{c['count']}</td>"
                f"<td class='{color_class}'>{c['score']:.2f}</td></tr>"
            )
        rows = "".join(rows_html)
        return f"""
<div class="card">
  <div class="card-title">{title}</div>
  <table>
    <thead><tr><th>Курс</th><th>Отзывов</th><th>Оценка</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="card-sub" style="margin-top:8px;">Оценки на rating-источниках — по 1–5; на текстовых — по сентимент-прокси.</div>
</div>
"""
    return f"""
<div class="section">
  <div class="section-title">Курсы: лидеры и зоны роста</div>
  <div class="grid-2">
    {table(d['courses_top'], 'Топ-5 курсов', 'green')}
    {table(d['courses_bottom'], 'Антитоп: над чем работать', 'red', highlight_course='перплексити')}
  </div>
</div>
"""


def render_themes(d):
    rows = "".join(
        f"<tr><td>{t['theme']}</td>"
        f"<td>{t['mentions']}</td>"
        f"<td class='green'>{t['pos']}</td>"
        f"<td>{t['neu']}</td>"
        f"<td class='red'>{t['neg']}</td>"
        f"<td class='{ 'red' if t['neg_pct'] > 10 else 'yellow' if t['neg_pct'] > 5 else 'green' }'>"
        f"{t['neg_pct']}%</td></tr>"
        for t in d["themes"]
    )
    # фокусные темы
    focus_cards = []
    for t in d["themes"]:
        if t["theme"].lower() in ("продажи", "цена"):
            color = "red" if t["neg_pct"] > 10 else "yellow"
            focus_cards.append(f"""
<div class="card">
  <div class="card-title {color}">Тема «{t['theme']}» — повышенное внимание</div>
  <div class="card-value {color}">{t['neg_pct']}%</div>
  <div class="card-sub">негативных упоминаний из {t['mentions']} ({t['neg']} негативных, {t['pos']} позитивных)</div>
</div>
""")
    focus_block = ""
    if focus_cards:
        focus_block = f'<div class="grid-2" style="margin-bottom:16px;">{"".join(focus_cards)}</div>'

    return f"""
<div class="section">
  <div class="section-title">Темы: сильные и слабые места</div>
  {focus_block}
  <div class="grid-2">
    <div class="card">
      <div class="card-title">Распределение упоминаний по темам</div>
      <div class="chart-wrap-lg"><canvas id="chartThemes"></canvas></div>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>Тема</th><th>Упоминаний</th><th>+</th><th>0</th><th>—</th><th>% негатива</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div class="card-sub" style="margin-top:8px;">Сентимент определяется по рейтингу (если есть) или лексикону.</div>
    </div>
  </div>
</div>
"""


def _quote_cards(items):
    if not items:
        return '<div class="card-sub">нет данных</div>'
    parts = []
    for it in items:
        if not isinstance(it, dict):
            continue
        quote = (it.get("quote") or "").replace('"', "&quot;")
        text = it.get("text", "")
        source = it.get("source", "")
        course = it.get("course", "")
        meta = " · ".join(x for x in (source, course) if x)
        parts.append(f"""<div class="quote-card">
  <div class="quote-text">«{quote}»</div>
  <div class="card-sub" style="margin-top:8px;"><b>{text}</b></div>
  <span class="quote-name">{meta}</span>
</div>""")
    return "".join(parts) if parts else '<div class="card-sub">нет данных</div>'


def render_insights(d):
    insights = d.get("insights") or {}
    if not insights:
        return """
<div class="section">
  <div class="section-title">Инсайты для продаж и маркетинга</div>
  <div class="card">
    <div class="card-title">Раздел в работе</div>
    <div class="card-sub">Запусти подагент <code>insights-extractor</code>, чтобы заполнить этот блок цитатами из отзывов.</div>
  </div>
</div>
"""
    cat_meta = [
        ("why_chosen", "Почему выбирают", "green"),
        ("strengths",  "Что зашло",       "green"),
        ("objections", "Возражения до покупки", "yellow"),
        ("weaknesses", "Что не зашло",    "red"),
    ]
    blocks = []
    for key, title, color in cat_meta:
        items = insights.get(key) or []
        blocks.append(f"""
<div class="card">
  <div class="card-title {color}">{title}</div>
  <div class="quotes-grid" style="margin-top:10px;">{_quote_cards(items)}</div>
</div>
""")

    # дополнительный блок: Перплексити + темы Продажи/Цена
    extra_html = ""
    perplexity = insights.get("perplexity_special") or []
    theme_sales = insights.get("theme_sales") or []
    theme_price = insights.get("theme_price") or []
    landing = insights.get("landing_quotes") or []

    if perplexity:
        extra_html += f"""
<div class="card" style="margin-top:16px;border-left:3px solid #F87171;">
  <div class="card-title red">Перплексити — голос боли (n=65, оценка 1.40)</div>
  <div class="quotes-grid" style="margin-top:10px;">{_quote_cards(perplexity)}</div>
</div>
"""
    if theme_sales or theme_price:
        sales_block = f"""
<div class="card">
  <div class="card-title red">Продажи — 19.2% негатива</div>
  <div class="quotes-grid" style="margin-top:10px;">{_quote_cards(theme_sales)}</div>
</div>""" if theme_sales else ""
        price_block = f"""
<div class="card">
  <div class="card-title yellow">Цена — 10.4% негатива</div>
  <div class="quotes-grid" style="margin-top:10px;">{_quote_cards(theme_price)}</div>
</div>""" if theme_price else ""
        extra_html += f'<div class="grid-2" style="margin-top:16px;">{sales_block}{price_block}</div>'

    if landing:
        extra_html += f"""
<div class="card" style="margin-top:16px;">
  <div class="card-title green">Цитаты для лендинга и маркетинга</div>
  <div class="quotes-grid" style="margin-top:10px;">{_quote_cards(landing)}</div>
</div>
"""

    return f"""
<div class="section">
  <div class="section-title">Инсайты для продаж и маркетинга</div>
  <div class="grid-2">{''.join(blocks)}</div>
  {extra_html}
</div>
"""


def render_monthly(d):
    return """
<div class="section">
  <div class="section-title">Динамика по месяцам</div>
  <div class="card">
    <div class="card-title">Объём отзывов и средний рейтинг</div>
    <div class="chart-wrap-xl"><canvas id="chartMonthly"></canvas></div>
  </div>
</div>
"""


def render_scripts(d):
    src_labels = [SOURCE_LABEL.get(s["source"], s["source"]) for s in d["by_source"]]
    src_counts = [s["count"] for s in d["by_source"]]
    src_ratings = [s["avg_rating_5"] if s["avg_rating_5"] is not None else None for s in d["by_source"]]
    theme_labels = [t["theme"] for t in d["themes"]]
    theme_pos = [t["pos"] for t in d["themes"]]
    theme_neu = [t["neu"] for t in d["themes"]]
    theme_neg = [t["neg"] for t in d["themes"]]
    month_labels = [m["month"] for m in d["monthly"]]
    month_counts = [m["count"] for m in d["monthly"]]
    month_ratings = [m["avg_rating_5"] for m in d["monthly"]]
    payload = {
        "srcLabels": src_labels, "srcCounts": src_counts, "srcRatings": src_ratings,
        "themeLabels": theme_labels, "themePos": theme_pos, "themeNeu": theme_neu, "themeNeg": theme_neg,
        "monthLabels": month_labels, "monthCounts": month_counts, "monthRatings": month_ratings,
    }
    return f"""
<script>
const D = {json.dumps(payload, ensure_ascii=False)};
const palette = {{ green:'#4ADE80', purple:'#A78BFA', yellow:'#FACC15', red:'#F87171', muted:'#9CA3AF' }};
const baseOpts = {{
  responsive: true, maintainAspectRatio: false,
  plugins: {{ legend: {{ labels: {{ color: '#E5E7EB' }} }} }},
  scales: {{
    x: {{ ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
    y: {{ ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
  }}
}};

new Chart(document.getElementById('chartSources'), {{
  type: 'bar',
  data: {{
    labels: D.srcLabels,
    datasets: [
      {{ label: 'Отзывов', data: D.srcCounts, backgroundColor: palette.purple, yAxisID: 'y' }},
      {{ label: 'Ср. рейтинг', data: D.srcRatings, backgroundColor: palette.yellow, yAxisID: 'y1', type: 'line', borderColor: palette.yellow, tension: 0.3 }},
    ]
  }},
  options: {{
    ...baseOpts,
    scales: {{
      x: {{ ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
      y:  {{ position:'left', ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
      y1: {{ position:'right', min: 0, max: 5, ticks: {{ color: palette.muted }}, grid: {{ display: false }} }},
    }}
  }}
}});

new Chart(document.getElementById('chartThemes'), {{
  type: 'bar',
  data: {{
    labels: D.themeLabels,
    datasets: [
      {{ label: 'Положительные', data: D.themePos, backgroundColor: palette.green }},
      {{ label: 'Нейтральные',  data: D.themeNeu, backgroundColor: palette.muted }},
      {{ label: 'Негативные',   data: D.themeNeg, backgroundColor: palette.red }},
    ]
  }},
  options: {{
    ...baseOpts,
    indexAxis: 'y',
    scales: {{
      x: {{ stacked: true, ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
      y: {{ stacked: true, ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
    }}
  }}
}});

new Chart(document.getElementById('chartMonthly'), {{
  type: 'bar',
  data: {{
    labels: D.monthLabels,
    datasets: [
      {{ label: 'Отзывов', data: D.monthCounts, backgroundColor: palette.purple, yAxisID: 'y' }},
      {{ label: 'Ср. рейтинг', data: D.monthRatings, borderColor: palette.yellow, backgroundColor: palette.yellow, yAxisID: 'y1', type: 'line', tension: 0.3, spanGaps: true }},
    ]
  }},
  options: {{
    ...baseOpts,
    scales: {{
      x: {{ ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
      y: {{ position:'left', ticks: {{ color: palette.muted }}, grid: {{ color: '#333' }} }},
      y1: {{ position:'right', min: 0, max: 5, ticks: {{ color: palette.muted }}, grid: {{ display: false }} }},
    }}
  }}
}});
</script>
"""


CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:#1C1C1C; --card:#2A2A2A; --card2:#323232; --border:#3F3F46;
  --green:#4ADE80; --purple:#A78BFA; --yellow:#FACC15; --red:#F87171;
  --text:#E5E7EB; --muted:#9CA3AF;
}
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.5; }
a { color: var(--purple); text-decoration: none; }
.header { background: #212121; border-bottom: 1px solid var(--border); padding: 18px 32px; display: flex; align-items: center; justify-content: space-between; }
.header-logo { font-size: 20px; font-weight: 700; color: var(--green); letter-spacing: -0.5px; }
.header-sub  { color: var(--muted); font-size: 13px; }
.header-date { color: var(--muted); font-size: 13px; text-align: right; }
.page { max-width: 1400px; margin: 0 auto; padding: 24px 24px 48px; }
.section { margin-bottom: 36px; }
.section-title { font-size: 13px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted); border-left: 3px solid var(--purple); padding-left: 10px; margin-bottom: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }
.card-title { font-size: 12px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.8px; }
.card-value { font-size: 32px; font-weight: 700; line-height: 1; }
.card-sub { font-size: 12px; color: var(--muted); margin-top: 6px; }
.green { color: var(--green); } .yellow { color: var(--yellow); } .purple { color: var(--purple); } .red { color: var(--red); }
.chart-wrap   { position: relative; height: 240px; }
.chart-wrap-lg{ position: relative; height: 320px; }
.chart-wrap-xl{ position: relative; height: 380px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { color: var(--muted); font-weight: 500; text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; }
td { padding: 7px 10px; border-bottom: 1px solid #333; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,0.03); }
.quotes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.quote-card  { background: var(--card2); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.quote-text  { font-size: 13px; color: var(--text); line-height: 1.55; font-style: italic; }
.quote-name  { font-size: 11px; color: var(--muted); margin-top: 8px; display: block; }
code { background: #1f1f1f; padding: 1px 5px; border-radius: 4px; color: var(--purple); font-size: 12px; }
.footer { text-align: center; color: #555; font-size: 11px; margin-top: 48px; }
"""


def build_html(d):
    today = date.today().strftime("%d.%m.%Y")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zerocoder — Дашборд отзывов {today}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header-logo">Zerocoder · Дашборд отзывов</div>
    <div class="header-sub">Внешние площадки + внутренние отзывы GetCourse</div>
  </div>
  <div class="header-date">Обновлено: {today}<br>Снимок: {d['generated_at']}</div>
</div>

<div class="page">
{render_summary(d)}
{render_sources(d)}
{render_courses(d)}
{render_themes(d)}
{render_insights(d)}
{render_monthly(d)}
<div class="footer">Источник данных: <code>data/unified-reviews.csv</code> · агрегаты: <code>tmp/dashboard-data.json</code></div>
</div>
{render_scripts(d)}
</body>
</html>
"""


def main():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_html = REPORTS / f"{date.today().isoformat()}-reviews-dashboard.html"
    out_html.write_text(build_html(d), encoding="utf-8")
    write_sheets_csvs(d)
    print(f"Dashboard -> {out_html}")
    sheets = sorted(SHEETS.glob("*.csv"))
    print(f"Sheets CSVs ({len(sheets)}):")
    for p in sheets:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
