"""
Читает data/unified-reviews.csv и считает агрегаты:
  - summary
  - by_source
  - courses_top / courses_bottom
  - themes (контент, кураторы, платформа, цена, поддержка, продажи)
  - monthly (последние 12 месяцев)
Кладёт в tmp/dashboard-data.json. Блок insights оставляет пустым —
его дописывает insights-extractor.
"""

import csv
import json
import re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC          = PROJECT_ROOT / "data" / "unified-reviews.csv"
OUT          = PROJECT_ROOT / "tmp" / "dashboard-data.json"
MIN_COURSE_REVIEWS = 5

THEMES = {
    "Контент":   r"контент|материал|программ|лекци|урок|тем[аы]|объясн|подача|структур|домашк|задани",
    "Кураторы":  r"куратор|эксперт|наставник|преподавател|спикер|лектор|тьютор",
    "Платформа": r"платформ|getcourse|интерфейс|лаг|не работа|кабинет|сайт не|доступ к материал|глюч",
    "Цена":      r"цена|дорого|стоимост|рассрочк|скидк|деньги|кредит|переплат",
    "Поддержка": r"поддержк|тех\.?поддержк|обратная связь|отвеча|помог|связ|общени|сопровожд",
    "Продажи":   r"впарив|навязыв|обман|реклам|развод|втюх|спам|звон.*реклам|агресс",
}

POSITIVE_LEX = r"отличн|супер|круто|спасиб|рекоменду|зашл|понрав|здоров|польз|интересн|качествен|👍|🙌|💛|🚀|✨"
NEGATIVE_LEX = r"плох|ужас|разоч|не понрав|не рекоменд|развод|обман|зря|жале|кошмар|👎"


def parse_rating(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        v = float(s.replace(",", "."))
        return v if 1 <= v <= 5 else None
    except ValueError:
        return None


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def classify_sentiment(rating_5, text):
    """Используем rating, если есть. Если нет — лексикон."""
    if rating_5 is not None:
        if rating_5 >= 4:
            return "pos"
        if rating_5 <= 2:
            return "neg"
        return "neu"
    t = (text or "").lower()
    pos = bool(re.search(POSITIVE_LEX, t))
    neg = bool(re.search(NEGATIVE_LEX, t))
    if pos and not neg:
        return "pos"
    if neg and not pos:
        return "neg"
    return "neu"


def month_key(date_str):
    if not date_str or len(date_str) < 7:
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return d.strftime("%Y-%m")
    except ValueError:
        return None


def main():
    rows = []
    with open(SRC, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["_rating"] = parse_rating(r.get("rating_5"))
            r["_full_text"] = " ".join([r.get("text") or "",
                                        r.get("pros") or "",
                                        r.get("cons") or ""]).lower()
            r["_sentiment"] = classify_sentiment(r["_rating"], r["_full_text"])
            rows.append(r)

    # SUMMARY
    total = len(rows)
    with_reply = sum(1 for r in rows if r.get("reply"))
    avg_rating_global = avg([r["_rating"] for r in rows])

    # BY SOURCE
    src_groups = defaultdict(list)
    for r in rows:
        src_groups[r["source"]].append(r)
    by_source = []
    for src, lst in src_groups.items():
        by_source.append({
            "source": src,
            "count": len(lst),
            "avg_rating_5": avg([r["_rating"] for r in lst]),
            "with_reply_pct": round(
                100 * sum(1 for r in lst if r.get("reply")) / len(lst), 1
            ),
        })
    by_source.sort(key=lambda x: x["count"], reverse=True)

    # COURSES TOP / BOTTOM (исключаем unknown и курсы без рейтинга вовсе)
    course_groups = defaultdict(list)
    for r in rows:
        if r["course"] and r["course"] != "unknown":
            course_groups[r["course"]].append(r)
    course_stats = []
    for course, lst in course_groups.items():
        rated = [r["_rating"] for r in lst if r["_rating"] is not None]
        if len(rated) < MIN_COURSE_REVIEWS:
            # Если оценок мало, используем сентимент-прокси: pos=5, neg=2, neu=4.
            sent_score = [
                5 if r["_sentiment"] == "pos"
                else 2 if r["_sentiment"] == "neg"
                else 4
                for r in lst
            ]
            if len(sent_score) < MIN_COURSE_REVIEWS:
                continue
            score = round(sum(sent_score) / len(sent_score), 2)
            source_kind = "sentiment"
        else:
            score = round(sum(rated) / len(rated), 2)
            source_kind = "rating"
        course_stats.append({
            "course": course,
            "count": len(lst),
            "score": score,
            "score_source": source_kind,
        })
    course_stats.sort(key=lambda x: (x["score"], x["count"]), reverse=True)
    courses_top    = course_stats[:5]
    courses_bottom = sorted(course_stats, key=lambda x: (x["score"], -x["count"]))[:5]

    # THEMES
    theme_stats = []
    for name, pattern in THEMES.items():
        rx = re.compile(pattern, re.IGNORECASE)
        matched = [r for r in rows if rx.search(r["_full_text"])]
        if not matched:
            continue
        pos = sum(1 for r in matched if r["_sentiment"] == "pos")
        neg = sum(1 for r in matched if r["_sentiment"] == "neg")
        neu = sum(1 for r in matched if r["_sentiment"] == "neu")
        theme_stats.append({
            "theme": name,
            "mentions": len(matched),
            "pos": pos,
            "neg": neg,
            "neu": neu,
            "neg_pct": round(100 * neg / len(matched), 1),
        })
    theme_stats.sort(key=lambda x: x["mentions"], reverse=True)

    # MONTHLY — последние 12 месяцев
    month_groups = defaultdict(list)
    for r in rows:
        mk = month_key(r["date"])
        if mk:
            month_groups[mk].append(r)
    months_sorted = sorted(month_groups.keys(), reverse=True)[:12]
    monthly = []
    for mk in sorted(months_sorted):
        lst = month_groups[mk]
        monthly.append({
            "month": mk,
            "count": len(lst),
            "avg_rating_5": avg([r["_rating"] for r in lst]),
        })

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "total": total,
            "with_reply": with_reply,
            "with_reply_pct": round(100 * with_reply / total, 1) if total else 0,
            "avg_rating_5_global": avg_rating_global,
            "sources": len(by_source),
        },
        "by_source": by_source,
        "courses_top": courses_top,
        "courses_bottom": courses_bottom,
        "themes": theme_stats,
        "monthly": monthly,
        "insights": {},  # заполнит insights-extractor
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Краткая сводка
    print(f"Total {total}, with_reply {with_reply} ({data['summary']['with_reply_pct']}%)")
    print(f"Global avg rating: {avg_rating_global}")
    print("Top courses:")
    for c in courses_top:
        print(f"  {c['score']:.2f}  n={c['count']:3d}  {c['course']}")
    print("Bottom courses:")
    for c in courses_bottom:
        print(f"  {c['score']:.2f}  n={c['count']:3d}  {c['course']}")
    print("Themes (sorted by mentions):")
    for t in theme_stats:
        print(f"  {t['theme']:10s}  n={t['mentions']:4d}  neg={t['neg_pct']}%")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
