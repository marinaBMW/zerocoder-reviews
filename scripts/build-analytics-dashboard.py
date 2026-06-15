"""
Аналитический дашборд отзывов Zerocoder.
python scripts/build-analytics-dashboard.py → reports/YYYY-MM-DD-analytics-dashboard.html

Добавить внешнюю площадку:  положить reviews-{name}.json в data/WebReviews/ + строку в PLATFORM_LABELS
Добавить курс:               положить {course}-reviews.csv в Education/data/Reviews/ — подхватится само
Обновить урочные данные:     заменить LESSON_FEEDBACK_PATH на новый файл
"""

import csv
import io
import json
import re
import random
from collections import Counter
from pathlib import Path
from datetime import date

try:
    import pandas as pd
except ImportError:
    raise SystemExit("Установи pandas: pip install pandas")

# ── PATHS ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
DATA_WEB     = ROOT / "data" / "WebReviews"
DATA_REVIEWS = ROOT.parent / "data" / "Reviews"
REPORTS      = ROOT / "reports"

# ── ИСТОЧНИКИ ─────────────────────────────────────────────────────────────────
EXTERNAL_SKIP = {"otzovik-all"}  # дубликат секций, исключаем

PLATFORM_LABELS = {
    "otzovik-university-main": "Отзовик / Университет",
    "otzovik-intensiv-mobile": "Отзовик / Мобайл",
    "otzovik-intensiv-python": "Отзовик / Python",
    "otzovik-intensiv-prompt": "Отзовик / Промпт",
    "tutortop":   "TutorTop",
    "okursah":    "okursah.ru",
    "skill2go":   "Skill2Go",
    "irecommend": "iRecommend",
    "yandex":     "Яндекс Карты",
    "google":     "Google Maps",
    "2gis":       "2ГИС",
    "pgdv":       "pgdv.ru",
    "kurshub":    "KursHub",
}

# Обновить путь при получении нового файла с урочными данными
LESSON_FEEDBACK_PATH = DATA_REVIEWS / "2026-05-13-lesson-feedback-raw.csv"

# ── СТОП-СЛОВА ────────────────────────────────────────────────────────────────
STOPWORDS = {
    "и","в","на","с","по","что","это","не","а","как","за","из","от","но","так",
    "же","при","к","о","об","у","до","бы","или","да","ли","ни","со","то","уже",
    "ещё","всё","все","был","была","было","были","будет","есть","нет",
    "я","он","она","оно","они","мы","вы","его","её","их","им","ему","мне","тебе",
    "нам","вам","меня","тебя","нас","вас","себя","который","которая","которое",
    "которые","которых","которым","которыми","которого","которому","которой",
    "этот","эта","эти","тот","та","те","тех","тем","теми","мой","моя","моё",
    "мои","твой","твоя","наш","ваш","весь","вся","каждый","каждая","каждое",
    "очень","более","менее","также","тоже","только","лишь","именно","ведь","вот",
    "вообще","просто","можно","нужно","надо","там","здесь","тут","потому","когда",
    "если","хотя","зачем","почему","где","куда","откуда","кто","какой","какая",
    "какое","какие","уже","много","мало","чуть","совсем","почти","около","сразу",
    "потом","поэтому","тогда","везде","всегда","иногда","никогда","теперь",
    "снова","опять","наконец","однако","этого","этому","этом","этой","этих","этим",
    "хочу","хочет","хотел","хотела","хотели","может","могу","могут","нужен",
    "нужна","нужны","должен","должна","должны","стал","стала","стало","стали",
    "делать","сделать","делаю","делает","сделал","сделала","говорит","сказал",
    "курс","курса","курсе","курсы","курсов","курсам","курсах","курсу",
    "обучение","обучения","обучению","обучением","обучении",
    "программа","программы","урок","уроки","уроков","урока","уроке",
    "zerocoder","зерокодер","зерокодера","зерокодеру","университет",
    "занятие","занятия","задание","задания","модуль","модули","через",
    "после","перед","между","во","над","под","без","про","для","пор","раз",
    "чем","хоть","пока","рада","рад","тому","своё","своей","своих","своим",
    "своему","всего","самый","самая","самое","самые","один","одна","само",
    # Коннекторы и пустые слова
    "чтобы","такой","такая","такое","такие","этой","того","даже","ничего",
    "нибудь","никто","нигде","никак","никакой","каком","такому","самом",
    "этому","таким","какому","любой","любого","другой","другого","другие",
    "другим","своими","такими","потому","поэтому","зато","хотя","почему",
    "поэтому","которую","которому","которых","которыми","вроде","будто",
    # Продуктовые слова — очевидны из контекста, не несут инсайта
    "интенсив","интенсива","интенсиву","интенсивам","интенсивах","интенсивы",
    "интенсиве","вебинар","вебинара","вебинаре","вебинары","вебинаров",
    "вебинарам","вебинарах","обучался","обучалась","обучились",
    "прошел","прошла","прошли","прошло","пройти",
}

# ── ТЕКСТ ─────────────────────────────────────────────────────────────────────

def _clean(s):
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"[^\w\s]", " ", s.lower(), flags=re.UNICODE)

def _tokens(text):
    return [w for w in _clean(text).split() if len(w) > 3 and w not in STOPWORDS and not w.isdigit()]

def top_words(texts, n=25):
    c = Counter()
    for t in texts:
        c.update(_tokens(t))
    return [[w, cnt] for w, cnt in c.most_common(n)]

def top_bigrams(texts, n=12):
    c = Counter()
    for t in texts:
        toks = _tokens(t)
        c.update(f"{toks[i]} {toks[i+1]}" for i in range(len(toks)-1))
    return [[bg, cnt] for bg, cnt in c.most_common(n)]

# ── ЗАГРУЗКА ДАННЫХ ───────────────────────────────────────────────────────────

def load_external():
    rows = []
    for jf in sorted(DATA_WEB.glob("reviews-*.json")):
        name = jf.stem.replace("reviews-", "")
        if name in EXTERNAL_SKIP:
            continue
        label = PLATFORM_LABELS.get(name, name)
        data = json.loads(jf.read_text(encoding="utf-8"))
        for r in data:
            combined = " ".join(filter(None, [
                r.get("title", ""), r.get("text", ""),
                r.get("pros", ""), r.get("cons", ""),
            ]))
            rows.append({
                "date":         r.get("date", ""),
                "rating":       r.get("rating"),
                "text":         combined.strip(),
                "platform":     label,
                "platform_key": name,
                "quote":        (r.get("text") or r.get("title") or "")[:400],
                "name":         r.get("name", ""),
                "url":          r.get("url", ""),
            })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["rating"])
    df["rating"] = df["rating"].astype(int)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["month"] = df["month"].replace("NaT", pd.NA)
    return df


def load_courses():
    rows = []
    for cf in sorted(DATA_REVIEWS.glob("*-reviews.csv")):
        course = cf.stem.replace("-reviews", "")
        raw_text = cf.read_bytes().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw_text))
        header = None
        text_idx = date_idx = None
        for row in reader:
            if header is None:
                header = row
                text_idx = next(
                    (i for i, c in enumerate(header)
                     if "текст" in c.lower() or "text" in c.lower()), None
                )
                date_idx = next(
                    (i for i, c in enumerate(header)
                     if "создан" in c.lower() or "дата" in c.lower()), None
                )
                continue
            if text_idx is None or len(row) <= text_idx:
                continue
            text_val = row[text_idx].strip()
            date_val = row[date_idx].strip() if date_idx is not None and len(row) > date_idx else ""
            rows.append({
                "date":   pd.to_datetime(date_val, errors="coerce"),
                "text":   text_val,
                "course": course,
            })
    return pd.DataFrame(rows)


def load_lessons():
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            df = pd.read_csv(LESSON_FEEDBACK_PATH, encoding=enc, low_memory=False)
            break
        except Exception:
            continue
    else:
        raise SystemExit(f"Не удалось прочитать {LESSON_FEEDBACK_PATH}")
    df.columns = [c.strip('﻿"').strip() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    # Форвард-филл дат внутри групп урока
    df["Date"] = df.groupby(["Course", "Modul", "Lesson"], group_keys=False)["Date"].apply(
        lambda s: s.ffill()
    )
    df["grade_ok"] = df["Grade"].str.contains("Понравился", na=False)
    df["month"] = df["Date"].dt.to_period("M").astype(str)
    df["month"] = df["month"].replace("NaT", pd.NA)
    df["Comment"] = df["Comment"].fillna("").astype(str)
    return df

# ── МЕТРИКИ ───────────────────────────────────────────────────────────────────

def rating_by_month(df):
    grp = (df.dropna(subset=["month"])
             .groupby("month", as_index=False)
             .agg(avg=("rating", "mean"), count=("rating", "size"))
             .sort_values("month"))
    grp["avg"] = grp["avg"].round(2)
    return grp.to_dict("records")


def rating_by_platform(df):
    grp = (df.groupby("platform", as_index=False)
             .agg(avg=("rating", "mean"),
                  count=("rating", "size"),
                  pct_pos=("rating", lambda x: round((x >= 4).mean() * 100, 1)))
             .sort_values("avg", ascending=False))
    grp["avg"] = grp["avg"].round(2)
    return grp.to_dict("records")


def lesson_by_month(df):
    grp = (df.dropna(subset=["month"])
             .groupby("month", as_index=False)
             .agg(pct=("grade_ok", lambda x: round(x.mean() * 100, 1)),
                  count=("grade_ok", "size"))
             .sort_values("month"))
    return grp.to_dict("records")


def lesson_by_course(df):
    grp = (df.groupby("Course", as_index=False)
             .agg(pct=("grade_ok", lambda x: round(x.mean() * 100, 1)),
                  count=("grade_ok", "size"))
             .sort_values("pct"))
    return grp.to_dict("records")


def get_neg_quotes(df, n=5):
    neg = df[(df["rating"] <= 2) & (df["quote"].str.len() > 40)].copy()
    if len(neg) > n:
        neg = neg.sample(n, random_state=42)
    out = []
    for _, r in neg.iterrows():
        out.append({
            "quote":    r["quote"],
            "platform": r["platform"],
            "date":     str(r["date"])[:10] if pd.notna(r["date"]) else "",
            "rating":   int(r["rating"]),
            "name":     r.get("name", ""),
        })
    return out


# ── HTML ──────────────────────────────────────────────────────────────────────

def _j(obj):
    return json.dumps(obj, ensure_ascii=False)

def build_html(
    total_ext, avg_rating, pct_pos_ext,
    total_courses, total_lessons, pct_ok_lessons,
    ext_min_month, ext_max_month, les_min_month,
    rating_months, platforms, lesson_months, courses_sat,
    kw, neg_quotes, low_platforms,
):
    today = date.today().strftime("%d.%m.%Y")

    # Chart data
    rm_labels = _j([r["month"] for r in rating_months])
    rm_data   = _j([r["avg"]   for r in rating_months])
    rm_counts = _j([r["count"] for r in rating_months])

    pl_labels = _j([p["platform"] for p in platforms])
    pl_data   = _j([p["avg"]      for p in platforms])
    pl_counts = _j([p["count"]    for p in platforms])
    pl_pct    = _j([p["pct_pos"]  for p in platforms])
    pl_colors = _j(["#4ADE80" if p["avg"] >= 4 else "#FACC15" if p["avg"] >= 3 else "#F87171"
                    for p in platforms])

    lm_labels = _j([m["month"] for m in lesson_months])
    lm_data   = _j([m["pct"]   for m in lesson_months])
    lm_counts = _j([m["count"] for m in lesson_months])

    # Bottom 10 + Top 5 courses
    cs_bottom = courses_sat[:10]
    cs_top    = sorted(courses_sat, key=lambda x: x["pct"], reverse=True)[:5]
    cs_labels = _j([c["Course"] for c in cs_bottom])
    cs_data   = _j([c["pct"]   for c in cs_bottom])
    cs_counts = _j([c["count"] for c in cs_bottom])
    cs_colors = _j(["#F87171" if c["pct"] < 80 else "#FACC15" for c in cs_bottom])

    pw_labels = _j([w[0] for w in kw["pos_words"]])
    pw_data   = _j([w[1] for w in kw["pos_words"]])
    nw_labels = _j([w[0] for w in kw["neg_words"]])
    nw_data   = _j([w[1] for w in kw["neg_words"]])

    # Point A labels
    point_a_ext = ext_min_month if ext_min_month != "nan" else "—"
    point_a_les = les_min_month if les_min_month != "nan" else "—"

    # Rating at point A vs now
    rating_a   = rating_months[0]["avg"]  if rating_months else "—"
    rating_now = rating_months[-1]["avg"] if rating_months else "—"
    les_a      = lesson_months[0]["pct"]  if lesson_months else "—"
    les_now    = lesson_months[-1]["pct"] if lesson_months else "—"

    # Negative quotes HTML
    def stars(n):
        return "★" * n + "☆" * (5 - n)

    quotes_html = ""
    for q in neg_quotes:
        quotes_html += f"""
        <div class="quote-card">
            <div class="quote-header">
                <span class="stars neg">{stars(q['rating'])}</span>
                <span class="quote-meta">{q['platform']} · {q['date']}</span>
            </div>
            <p class="quote-text">«{q['quote']}»</p>
            <span class="quote-name">{q['name']}</span>
        </div>"""

    # Low platforms table
    low_pl_rows = ""
    for p in low_platforms[:8]:
        neg_count = int(round(p["count"] * (100 - p["pct_pos"]) / 100))
        color = "#F87171" if p["pct_pos"] < 80 else "#FACC15"
        low_pl_rows += f"""<tr>
            <td>{p['platform']}</td>
            <td style="color:{color};font-weight:600">{p['pct_pos']:.0f}%</td>
            <td style="color:#9CA3AF">{neg_count} / {int(p['count'])}</td>
        </tr>"""

    # Low courses table (bottom 10)
    low_cs_rows = ""
    for c in cs_bottom:
        color = "#F87171" if c["pct"] < 80 else "#FACC15"
        low_cs_rows += f"""<tr>
            <td>{c['Course']}</td>
            <td style="color:{color};font-weight:600">{c['pct']:.0f}%</td>
            <td style="color:#9CA3AF">{int(c['count'])}</td>
        </tr>"""

    # Bigrams HTML
    def bigrams_html(bg_list, color):
        items = ""
        for i, (bg, cnt) in enumerate(bg_list):
            items += f'<div class="bigram-item"><span class="bigram-rank" style="color:{color}">#{i+1}</span><span class="bigram-text">{bg}</span><span class="bigram-count" style="color:{color}">{cnt}</span></div>'
        return items

    pos_bigrams_html = bigrams_html(kw["pos_bigrams"], "#4ADE80")
    neg_bigrams_html = bigrams_html(kw["neg_bigrams"], "#F87171")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zerocoder — Аналитика отзывов {today}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:      #1C1C1C;
  --card:    #2A2A2A;
  --card2:   #323232;
  --border:  #3F3F46;
  --green:   #4ADE80;
  --purple:  #A78BFA;
  --yellow:  #FACC15;
  --red:     #F87171;
  --text:    #E5E7EB;
  --muted:   #9CA3AF;
}}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
}}
a {{ color: var(--purple); text-decoration: none; }}

/* ── HEADER ── */
.header {{
  background: #212121;
  border-bottom: 1px solid var(--border);
  padding: 18px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.header-logo {{ font-size: 20px; font-weight: 700; color: var(--green); letter-spacing: -0.5px; }}
.header-sub  {{ color: var(--muted); font-size: 13px; }}
.header-date {{ color: var(--muted); font-size: 13px; text-align: right; }}

/* ── LAYOUT ── */
.page {{ max-width: 1400px; margin: 0 auto; padding: 24px 24px 48px; }}
.section {{ margin-bottom: 36px; }}
.section-title {{
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--muted);
  border-left: 3px solid var(--purple);
  padding-left: 10px;
  margin-bottom: 16px;
}}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
.grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}

/* ── CARDS ── */
.card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
}}
.card-sm {{ padding: 16px; }}
.card-title {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.8px; }}
.card-value {{ font-size: 32px; font-weight: 700; line-height: 1; }}
.card-sub {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}
.card-badge {{
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 99px;
  margin-top: 6px;
}}
.green  {{ color: var(--green);  }}
.yellow {{ color: var(--yellow); }}
.purple {{ color: var(--purple); }}
.red    {{ color: var(--red);    }}

/* ── CHART WRAPPER ── */
.chart-wrap {{ position: relative; height: 240px; }}
.chart-wrap-lg {{ position: relative; height: 320px; }}
.chart-wrap-xl {{ position: relative; height: 380px; }}

/* ── POINT A BADGE ── */
.point-a-row {{
  display: flex;
  gap: 24px;
  margin-top: 10px;
  font-size: 12px;
}}
.point-a-item {{ display: flex; flex-direction: column; }}
.point-a-label {{ color: var(--muted); font-size: 11px; }}
.point-a-val   {{ font-weight: 700; font-size: 16px; }}

/* ── KEYWORDS ── */
.kw-section {{ display: flex; gap: 16px; }}
.kw-col     {{ flex: 1; }}
.kw-title   {{ font-size: 12px; font-weight: 600; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.8px; }}

/* ── BIGRAMS ── */
.bigrams-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
.bigram-item  {{ display: flex; align-items: baseline; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); }}
.bigram-rank  {{ font-size: 11px; font-weight: 600; min-width: 24px; }}
.bigram-text  {{ flex: 1; font-size: 13px; }}
.bigram-count {{ font-size: 12px; font-weight: 600; min-width: 28px; text-align: right; }}

/* ── TABLES ── */
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ color: var(--muted); font-weight: 500; text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; }}
td {{ padding: 7px 10px; border-bottom: 1px solid #333; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(255,255,255,0.03); }}

/* ── QUOTES ── */
.quotes-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.quote-card  {{ background: var(--card2); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }}
.quote-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.stars {{ font-size: 13px; letter-spacing: 2px; }}
.stars.neg {{ color: var(--red); }}
.quote-meta {{ font-size: 11px; color: var(--muted); }}
.quote-text {{ font-size: 13px; color: var(--text); line-height: 1.55; font-style: italic; }}
.quote-name {{ font-size: 11px; color: var(--muted); margin-top: 8px; display: block; }}

/* ── TOP 5 BEST COURSES ── */
.top5 {{ margin-top: 12px; }}
.top5-item {{ display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 13px; }}
.top5-item:last-child {{ border-bottom: none; }}

/* ── FOOTER ── */
.footer {{ text-align: center; color: #555; font-size: 11px; margin-top: 48px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header-logo">Zerocoder · Аналитика отзывов</div>
    <div class="header-sub">Внешние площадки + курсовые + урочные отзывы</div>
  </div>
  <div class="header-date">Обновлено: {today}</div>
</div>

<div class="page">

<!-- ── БЛОК 1: СВОДКА ── -->
<div class="section">
  <div class="section-title">Сводные показатели</div>
  <div class="grid-4">
    <div class="card">
      <div class="card-title">Внешние отзывы</div>
      <div class="card-value green">{total_ext}</div>
      <div class="card-sub">{len(platforms)} площадок</div>
    </div>
    <div class="card">
      <div class="card-title">Средний рейтинг</div>
      <div class="card-value yellow">{avg_rating}★</div>
      <div class="card-sub">{pct_pos_ext}% положительных (4–5★)</div>
    </div>
    <div class="card">
      <div class="card-title">Курсовые отзывы</div>
      <div class="card-value purple">{total_courses}</div>
      <div class="card-sub">текстовых отзывов после курсов</div>
    </div>
    <div class="card">
      <div class="card-title">Оценки уроков</div>
      <div class="card-value green">{pct_ok_lessons}%</div>
      <div class="card-sub">«Понравился» из {total_lessons:,} оценок</div>
    </div>
  </div>
</div>

<!-- ── БЛОК 2: УДОВЛЕТВОРЁННОСТЬ ── -->
<div class="section">
  <div class="section-title">Удовлетворённость: тренд и источники</div>
  <div class="grid-2">

    <!-- Рейтинг по месяцам -->
    <div class="card">
      <div class="card-title">Средний рейтинг внешних отзывов по месяцам</div>
      <div class="chart-wrap">
        <canvas id="chartRatingMonths"></canvas>
      </div>
      <div class="point-a-row">
        <div class="point-a-item">
          <span class="point-a-label">Точка А ({point_a_ext})</span>
          <span class="point-a-val yellow">{rating_a}★</span>
        </div>
        <div class="point-a-item">
          <span class="point-a-label">Сейчас ({ext_max_month})</span>
          <span class="point-a-val green">{rating_now}★</span>
        </div>
      </div>
    </div>

    <!-- % Понравился по месяцам -->
    <div class="card">
      <div class="card-title">% «Понравился» по урокам — по месяцам</div>
      <div class="chart-wrap">
        <canvas id="chartLessonMonths"></canvas>
      </div>
      <div class="point-a-row">
        <div class="point-a-item">
          <span class="point-a-label">Точка А ({point_a_les})</span>
          <span class="point-a-val yellow">{les_a}%</span>
        </div>
        <div class="point-a-item">
          <span class="point-a-label">Сейчас</span>
          <span class="point-a-val green">{les_now}%</span>
        </div>
      </div>
    </div>

    <!-- Рейтинг по платформам -->
    <div class="card">
      <div class="card-title">Средний рейтинг по платформам</div>
      <div class="chart-wrap-lg">
        <canvas id="chartPlatforms"></canvas>
      </div>
    </div>

    <!-- Курсы: низкий % Понравился -->
    <div class="card">
      <div class="card-title">Удовлетворённость уроками по курсам (худшие 10)</div>
      <div class="chart-wrap-lg">
        <canvas id="chartCourses"></canvas>
      </div>
    </div>

  </div>
</div>

<!-- ── БЛОК 3: МАРКЕТИНГ ── -->
<div class="section">
  <div class="section-title">Маркетинг и продажи: боли и мотивации</div>
  <div class="grid-2">

    <div class="card">
      <div class="card-title" style="color:var(--green)">Ключевые слова в позитивных отзывах (мотивации)</div>
      <div class="chart-wrap-xl">
        <canvas id="chartPosWords"></canvas>
      </div>
    </div>

    <div class="card">
      <div class="card-title" style="color:var(--red)">Ключевые слова в негативных отзывах (боли)</div>
      <div class="chart-wrap-xl">
        <canvas id="chartNegWords"></canvas>
      </div>
    </div>

  </div>

  <div class="bigrams-grid" style="margin-top:16px;">
    <div class="card card-sm">
      <div class="kw-title green">Топ-фразы: мотивации</div>
      {pos_bigrams_html}
    </div>
    <div class="card card-sm">
      <div class="kw-title red">Топ-фразы: боли</div>
      {neg_bigrams_html}
    </div>
  </div>
</div>

<!-- ── БЛОК 4: СЛАБЫЕ МЕСТА ── -->
<div class="section">
  <div class="section-title">Слабые места</div>
  <div class="grid-3">

    <div class="card card-sm">
      <div class="card-title">Доля позитивных отзывов по площадкам</div>
      <table>
        <thead><tr><th>Площадка</th><th>% позит.</th><th>Негат./Всего</th></tr></thead>
        <tbody>{low_pl_rows}</tbody>
      </table>
    </div>

    <div class="card card-sm">
      <div class="card-title">Курсы с низкой удовлетворённостью (худшие 10)</div>
      <table>
        <thead><tr><th>Курс</th><th>% «Понравился»</th><th>Оценок</th></tr></thead>
        <tbody>{low_cs_rows}</tbody>
      </table>
    </div>

    <div class="card card-sm">
      <div class="card-title">Топ-5 курсов по удовлетворённости</div>
      <div class="top5">
        {''.join(f'<div class="top5-item"><span>{c["Course"]}</span><span class="green" style="font-weight:600">{c["pct"]:.0f}%</span></div>' for c in cs_top)}
      </div>
    </div>

  </div>

  <!-- Negative quotes -->
  <div style="margin-top:16px;">
    <div class="card-title" style="margin-bottom:12px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:0.8px;">Примеры негативных внешних отзывов (1–2★)</div>
    <div class="quotes-grid">
      {quotes_html}
    </div>
  </div>
</div>

<div class="footer">
  Zerocoder Reviews Dashboard · Данные: {ext_min_month} — {ext_max_month} (внешние) · {point_a_les} — сейчас (уроки)
</div>

</div><!-- /page -->

<script>
Chart.defaults.color = '#9CA3AF';
Chart.defaults.borderColor = '#3F3F46';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
Chart.defaults.font.size = 12;

// ── Rating by month ──
new Chart(document.getElementById('chartRatingMonths'), {{
  type: 'line',
  data: {{
    labels: {rm_labels},
    datasets: [{{
      label: 'Средний рейтинг',
      data: {rm_data},
      borderColor: '#4ADE80',
      backgroundColor: 'rgba(74,222,128,0.1)',
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: (ctx) => {{
            const counts = {rm_counts};
            return `Рейтинг: ${{ctx.parsed.y}}★ (n=${{counts[ctx.dataIndex]}})`;
          }}
        }}
      }}
    }},
    scales: {{
      y: {{ min: 1, max: 5, grid: {{ color: '#333' }}, ticks: {{ stepSize: 0.5 }} }},
      x: {{ grid: {{ display: false }}, ticks: {{ maxRotation: 45, maxTicksLimit: 12 }} }}
    }}
  }}
}});

// ── Lesson satisfaction by month ──
new Chart(document.getElementById('chartLessonMonths'), {{
  type: 'line',
  data: {{
    labels: {lm_labels},
    datasets: [{{
      label: '% Понравился',
      data: {lm_data},
      borderColor: '#A78BFA',
      backgroundColor: 'rgba(167,139,250,0.1)',
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: (ctx) => {{
            const counts = {lm_counts};
            return `Понравился: ${{ctx.parsed.y}}% (n=${{counts[ctx.dataIndex]}})`;
          }}
        }}
      }}
    }},
    scales: {{
      y: {{ min: 50, max: 100, grid: {{ color: '#333' }}, ticks: {{ callback: v => v + '%' }} }},
      x: {{ grid: {{ display: false }}, ticks: {{ maxRotation: 45, maxTicksLimit: 10 }} }}
    }}
  }}
}});

// ── Platforms bar ──
new Chart(document.getElementById('chartPlatforms'), {{
  type: 'bar',
  data: {{
    labels: {pl_labels},
    datasets: [{{
      label: 'Средний рейтинг',
      data: {pl_data},
      backgroundColor: {pl_colors},
      borderRadius: 4,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: (ctx) => {{
            const counts = {pl_counts};
            const pcts   = {pl_pct};
            return [`${{ctx.parsed.x}}★`, `${{counts[ctx.dataIndex]}} отзывов`, `${{pcts[ctx.dataIndex]}}% позит.`];
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ min: 1, max: 5, grid: {{ color: '#333' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// ── Courses satisfaction ──
new Chart(document.getElementById('chartCourses'), {{
  type: 'bar',
  data: {{
    labels: {cs_labels},
    datasets: [{{
      label: '% Понравился',
      data: {cs_data},
      backgroundColor: {cs_colors},
      borderRadius: 4,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: (ctx) => {{
            const counts = {cs_counts};
            return [`${{ctx.parsed.x}}%`, `${{counts[ctx.dataIndex]}} оценок`];
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ min: 0, max: 100, grid: {{ color: '#333' }}, ticks: {{ callback: v => v + '%' }} }},
      y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});

// ── Positive keywords ──
new Chart(document.getElementById('chartPosWords'), {{
  type: 'bar',
  data: {{
    labels: {pw_labels},
    datasets: [{{
      label: 'Упоминаний',
      data: {pw_data},
      backgroundColor: 'rgba(74,222,128,0.75)',
      borderRadius: 3,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#333' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// ── Negative keywords ──
new Chart(document.getElementById('chartNegWords'), {{
  type: 'bar',
  data: {{
    labels: {nw_labels},
    datasets: [{{
      label: 'Упоминаний',
      data: {nw_data},
      backgroundColor: 'rgba(248,113,113,0.75)',
      borderRadius: 3,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#333' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

</script>
</body>
</html>"""


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Аналитический дашборд Zerocoder — {date.today()}")
    print("=" * 50)

    print("Загружаю внешние отзывы...")
    ext_df = load_external()
    print(f"  {len(ext_df)} отзывов, {ext_df['platform'].nunique()} площадок")

    print("Загружаю курсовые отзывы...")
    course_df = load_courses()
    print(f"  {len(course_df)} отзывов по {course_df['course'].nunique()} курсам")

    print("Загружаю урочные оценки...")
    les_df = load_lessons()
    print(f"  {len(les_df)} оценок")

    print("Считаю метрики...")
    total_ext      = len(ext_df)
    avg_rating     = round(float(ext_df["rating"].mean()), 2)
    pct_pos_ext    = round(float((ext_df["rating"] >= 4).mean() * 100), 1)
    total_courses  = len(course_df)
    total_lessons  = len(les_df)
    pct_ok_lessons = round(float(les_df["grade_ok"].mean() * 100), 1)

    rating_months = rating_by_month(ext_df)
    platforms_data = rating_by_platform(ext_df)
    lesson_months = lesson_by_month(les_df)
    courses_sat   = lesson_by_course(les_df)
    kw            = compute_keywords(ext_df, les_df, course_df)
    neg_quotes    = get_neg_quotes(ext_df)

    valid_months = ext_df["month"].dropna()
    ext_min_month = str(valid_months.min()) if len(valid_months) else "—"
    ext_max_month = str(valid_months.max()) if len(valid_months) else "—"
    les_months    = les_df["month"].dropna()
    les_min_month = str(les_months.min()) if len(les_months) else "—"

    low_platforms = sorted(
        [p for p in platforms_data if p["count"] >= 3],
        key=lambda x: x["pct_pos"]
    )

    print("Генерирую HTML...")
    REPORTS.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS / f"{date.today()}-analytics-dashboard.html"
    html = build_html(
        total_ext=total_ext,
        avg_rating=avg_rating,
        pct_pos_ext=pct_pos_ext,
        total_courses=total_courses,
        total_lessons=total_lessons,
        pct_ok_lessons=pct_ok_lessons,
        ext_min_month=ext_min_month,
        ext_max_month=ext_max_month,
        les_min_month=les_min_month,
        rating_months=rating_months,
        platforms=platforms_data,
        lesson_months=lesson_months,
        courses_sat=courses_sat,
        kw=kw,
        neg_quotes=neg_quotes,
        low_platforms=low_platforms,
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"\nGotovo! -> {output_path}")


def compute_keywords(ext_df, les_df, course_df):
    pos_texts = (
        ext_df[ext_df["rating"] >= 4]["text"].tolist() +
        les_df[les_df["grade_ok"]]["Comment"].tolist() +
        course_df["text"].tolist()
    )
    neg_texts = (
        ext_df[ext_df["rating"] <= 2]["text"].tolist() +
        les_df[~les_df["grade_ok"]]["Comment"].tolist()
    )
    return {
        "pos_words":   top_words(pos_texts, 25),
        "neg_words":   top_words(neg_texts, 25),
        "pos_bigrams": top_bigrams(pos_texts, 12),
        "neg_bigrams": top_bigrams(neg_texts, 12),
    }


if __name__ == "__main__":
    main()
