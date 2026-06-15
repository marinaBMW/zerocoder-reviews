"""
Готовит рабочую таблицу неотвеченных внешних отзывов + предложенный ответ.

Фильтр:
  - reply == ""
  - source NOT IN ('gc', 'google')
  - date >= today - 6 months

На выход:
  - reports/{YYYY-MM-DD}-unanswered-reviews.md
  - reports/{YYYY-MM-DD}-unanswered-reviews.csv

Тон ответа базируется на reports/2026-06-08-gc-reviews.md.
Шаблон собирается из конкретики отзыва (имя, оценка, плюс/минус, упомянутый курс).
"""

import csv
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "data" / "unified-reviews.csv"
TODAY = date.today()
MONTHS_BACK = 6
CUTOFF = TODAY - timedelta(days=30 * MONTHS_BACK)

OUT_MD  = ROOT / "reports" / f"{TODAY.isoformat()}-unanswered-reviews.md"
OUT_CSV = ROOT / "reports" / f"{TODAY.isoformat()}-unanswered-reviews.csv"

SOURCE_LABEL = {
    "otzovik":    "Отзовик",
    "tutortop":   "TutorTop",
    "okursah":    "okursah.ru",
    "skill2go":   "skill2go",
    "2gis":       "2ГИС",
    "pgdv":       "pgdv.ru",
    "yandex":     "Яндекс Карты",
    "irecommend": "iRecommend",
    "kurshub":    "KursHub",
}

EXCLUDED_SOURCES = {"gc", "google"}


def parse_date(s):
    s = (s or "").strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def load_date_fallback():
    """Карта url -> date из исходных CSV площадок (даты в unified-reviews пустые)."""
    sources = ["otzovik", "tutortop", "okursah", "skill2go", "2gis",
               "pgdv", "yandex", "irecommend", "kurshub"]
    mp = {}
    for src in sources:
        path = ROOT / "data" / "WebReviews" / f"reviews-{src}.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                url = (r.get("url") or "").strip()
                dt  = (r.get("date") or "").strip()
                if url and dt:
                    mp[url] = dt
    return mp



def classify(rating, text):
    try:
        r = float(rating.replace(",", "."))
    except Exception:
        r = None
    if r is not None and r >= 4:
        return "pos"
    if r is not None and r <= 2:
        return "neg"
    # текстовая эвристика
    t = (text or "").lower()
    if re.search(r"плох|ужас|разоч|не понрав|не рекоменд|развод|обман|зря|жале", t):
        return "neg"
    if re.search(r"отличн|супер|круто|спасиб|рекоменду|зашл|понрав|польз", t):
        return "pos"
    return "neu"


def extract_topic(text, pros, cons):
    """Достаёт 1-2 коротких фразы, которые можно вернуть в ответе как «зеркало»."""
    snippets = []
    for raw in (pros, cons, text):
        if not raw:
            continue
        for piece in re.split(r"[.!?\n]+", raw):
            p = piece.strip()
            if 12 <= len(p) <= 100:
                snippets.append(p)
            if len(snippets) >= 2:
                break
        if len(snippets) >= 2:
            break
    return snippets[:2]


def detect_course(course, text):
    """Возвращает короткое имя курса для упоминания в ответе."""
    if course and course != "unknown":
        return course.lower()
    t = (text or "").lower()
    if "промпт" in t: return "курс по промпт-инжинирингу"
    if "питон" in t or "python" in t: return "курс по Python с ChatGPT"
    if "нейросет" in t: return "курс по нейросетям"
    if "чат-бот" in t or "salebot" in t: return "курс по чат-ботам"
    if "мобиль" in t or "flutter" in t: return "курс по мобильной разработке"
    if "perplex" in t or "перплекс" in t: return "курс по Perplexity"
    return None


def first_name(name):
    if not name:
        return None
    # часто это ник; берём первую часть
    first = name.split(",")[0].strip().split()[0] if name else ""
    if len(first) < 2 or first.isdigit():
        return None
    # ник-стайл: содержит цифры / латиницу — упростим
    if re.search(r"\d", first):
        return None
    return first


def draft_reply(row):
    sentiment = classify(row.get("rating_5", ""), row.get("text", ""))
    name = first_name(row.get("name", ""))
    course = detect_course(row.get("course", ""), row.get("text", ""))
    snippets = extract_topic(row.get("text", ""), row.get("pros", ""), row.get("cons", ""))

    greeting = f"{name}, " if name else ""

    if sentiment == "pos":
        opener = "спасибо за тёплый отзыв"
        if snippets:
            mirror = f" — приятно слышать про «{snippets[0]}»"
        else:
            mirror = ""
        course_part = f". Здорово, что {course} оказался полезным" if course else ""
        closing = " Желаем, чтобы инструменты дальше приносили результат и интересные задачи!"
    elif sentiment == "neg":
        opener = "спасибо, что поделились — нам важно это услышать"
        if snippets:
            mirror = f". То, что вы описали («{snippets[0]}»), обязательно передадим команде"
        else:
            mirror = ". Все замечания обязательно передадим команде"
        course_part = f". По {course} уже смотрим, что можно улучшить" if course else ""
        closing = " Спасибо, что дали нам возможность стать лучше."
    else:
        opener = "спасибо за подробный отзыв"
        if snippets:
            mirror = f" — особенно за акцент на «{snippets[0]}»"
        else:
            mirror = ""
        course_part = f". По {course} ваш фидбэк обязательно учтём" if course else ""
        closing = " Желаем интересных задач и результатов!"

    return f"{greeting.capitalize() if not name else greeting}{opener}{mirror}{course_part}.{closing}"


def main():
    date_fallback = load_date_fallback()
    rows = []
    with open(SRC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["source"] in EXCLUDED_SOURCES:
                continue
            if r.get("reply"):
                continue
            raw_date = r.get("date") or date_fallback.get(r.get("url", ""), "")
            r["date"] = raw_date  # пробросим в выгрузку
            d = parse_date(raw_date)
            if d is None or d < CUTOFF:
                continue
            r["_date"] = d
            r["_sentiment"] = classify(r.get("rating_5"), r.get("text"))
            r["_reply_suggested"] = draft_reply(r)
            rows.append(r)

    # сортировка: сначала свежие, внутри площадки — негатив выше
    sentiment_order = {"neg": 0, "neu": 1, "pos": 2}
    rows.sort(key=lambda r: (r["source"], sentiment_order[r["_sentiment"]], -r["_date"].toordinal()))

    # CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "source", "name", "rating_5", "course",
                    "text", "pros", "cons", "url", "suggested_reply", "sentiment"])
        for r in rows:
            w.writerow([
                r["date"], SOURCE_LABEL.get(r["source"], r["source"]),
                r["name"], r["rating_5"], r["course"],
                r["text"], r["pros"], r["cons"], r["url"],
                r["_reply_suggested"], r["_sentiment"],
            ])

    # MD — группируем по площадкам, внутри сначала негатив
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Неотвеченные внешние отзывы — {TODAY.isoformat()}",
        "",
        f"Окно: последние {MONTHS_BACK} мес. (с {CUTOFF.isoformat()}). Источников: GC и Google исключены.",
        "",
        f"**Итого: {len(rows)} отзывов без ответа.**",
        "",
    ]
    from collections import defaultdict
    by_src = defaultdict(list)
    for r in rows:
        by_src[r["source"]].append(r)
    for src in sorted(by_src.keys(), key=lambda s: -len(by_src[s])):
        lst = by_src[src]
        neg_n = sum(1 for r in lst if r["_sentiment"] == "neg")
        lines.append(f"## {SOURCE_LABEL.get(src, src)} — {len(lst)} отзывов (негативных: {neg_n})")
        lines.append("")
        for i, r in enumerate(lst, 1):
            badge = {"neg": "🔴", "neu": "🟡", "pos": "🟢"}[r["_sentiment"]]
            rating = f" — {r['rating_5']}★" if r['rating_5'] else ""
            name = r["name"] or "—"
            course = r["course"] if r["course"] != "unknown" else ""
            text = r["text"].strip()
            if len(text) > 600:
                text = text[:600] + "…"
            lines.append(f"### {badge} #{i} · {r['date']} · {name}{rating}")
            if course:
                lines.append(f"_{course}_")
            lines.append("")
            lines.append(f"> {text}")
            if r["pros"]:
                lines.append(f"> **Плюсы:** {r['pros']}")
            if r["cons"]:
                lines.append(f"> **Минусы:** {r['cons']}")
            lines.append("")
            lines.append(f"**Предлагаемый ответ:**")
            lines.append("")
            lines.append(r["_reply_suggested"])
            lines.append("")
            if r["url"]:
                lines.append(f"[Открыть на площадке]({r['url']})")
            lines.append("")
            lines.append("---")
            lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Unanswered reviews: {len(rows)}")
    for src, lst in sorted(by_src.items(), key=lambda x: -len(x[1])):
        neg = sum(1 for r in lst if r['_sentiment'] == 'neg')
        print(f"  {SOURCE_LABEL.get(src, src):14s}  {len(lst):4d}  (negative: {neg})")
    print(f"\nMD  -> {OUT_MD}")
    print(f"CSV -> {OUT_CSV}")


if __name__ == "__main__":
    main()
