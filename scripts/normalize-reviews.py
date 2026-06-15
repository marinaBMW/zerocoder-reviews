"""
Сводит все источники отзывов (GC-Reviews + WebReviews) в единый файл
data/unified-reviews.csv со схемой:
    source, date, name, rating_5, course, text, pros, cons, reply, url

- GC-Reviews: source=gc, name=email, rating пусто. Ответ куратора
  (Email = bogachova11051989@gmail.com) идущий сразу после студенческого
  отзыва в той же группе/курсе подклеивается в поле reply.
- Otzovik:    source=otzovik
- External:   source = домен (irecommend / yandex / 2gis)
- Google:     source=google
"""

import csv
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
GC_DIR       = PROJECT_ROOT / "data" / "GC-Reviews"
WEB_DIR      = PROJECT_ROOT / "data" / "WebReviews"
OUT_PATH     = PROJECT_ROOT / "data" / "unified-reviews.csv"
CURATOR_EMAIL = "bogachova11051989@gmail.com"

FIELDS = ["source", "date", "name", "rating_5", "course",
          "text", "pros", "cons", "reply", "url"]

# Маппинг имени файла GC -> канонический курс
GC_COURSE_MAP = {
    "agent2.0":            "АГЕНТЫ 2.0",
    "airtable":            "AIRTABLE",
    "analyst":             "АНАЛИТИК ДАННЫХ С НУЛЯ",
    "chatbot":             "РАЗРАБОТЧИК ЧАТ-БОТОВ",
    "flutter":             "FLUTTER",
    "mobile":              "МОБИЛЬНАЯ РАЗРАБОТКА",
    "mobile-flutter":      "МОБИЛЬНАЯ РАЗРАБОТКА (FLUTTER)",
    "neuro":               "НЕЙРОСЕТИ: ОТ ПРИНЦИПОВ К ПРАКТИКЕ",
    "neuro-china":         "КИТАЙСКИЕ НЕЙРОСЕТИ",
    "neuro-law":           "НЕЙРОСЕТИ ДЛЯ ЮРИСТОВ",
    "neuro-life":          "НЕЙРОСЕТИ ДЛЯ ЖИЗНИ",
    "neuro-market":        "ВАЙБ-МАРКЕТИНГ",
    "neuro-money-2.0":     "НЕЙРОДЕНЬГИ 2.0",
    "neuro-russian":       "НЕЙРОСЕТИ С РОССИЙСКИМИ ИНСТРУМЕНТАМИ",
    "neuro-teach":         "НЕЙРОСЕТИ ДЛЯ ПРЕПОДАВАТЕЛЯ",
    "perplexity":          "ПЕРПЛЕКСИТИ: ОТ НОВИЧКА ДО ПРО",
    "prompt-engineer":     "ПРОМПТ-ИНЖИНИРИНГ",
    "prompt-engineer-3.0": "ПРОМПТ-ИНЖИНИРИНГ 3.0",
    "python-ai":           "ПРОГРАММИСТ НА PYTHON С CHATGPT",
    "tilda":               "TILDA",
    "ux-ui":               "UX/UI",
    "vibe-code":           "ВАЙБ-КОДЕР",
    "web-design":          "ВЕБ-ДИЗАЙНЕР",
    "web":                 "ВЕБ-РАЗРАБОТКА",
}

# Ключевые слова для best-effort матчинга курса из текста отзыва.
KEYWORD_TO_COURSE = [
    (r"промпт[- ]?инжиниринг",       "ПРОМПТ-ИНЖИНИРИНГ"),
    (r"вайб[- ]?код",                "ВАЙБ-КОДЕР"),
    (r"вайб[- ]?маркетинг",          "ВАЙБ-МАРКЕТИНГ"),
    (r"чат[- ]?бот",                 "РАЗРАБОТЧИК ЧАТ-БОТОВ"),
    (r"мобильн|flutter",             "МОБИЛЬНАЯ РАЗРАБОТКА"),
    (r"аналитик данных",             "АНАЛИТИК ДАННЫХ С НУЛЯ"),
    (r"perplexity|перплекс",         "ПЕРПЛЕКСИТИ: ОТ НОВИЧКА ДО ПРО"),
    (r"нейросет.* для жизн",         "НЕЙРОСЕТИ ДЛЯ ЖИЗНИ"),
    (r"нейросет.* для юрист",        "НЕЙРОСЕТИ ДЛЯ ЮРИСТОВ"),
    (r"нейросет.* для препод",       "НЕЙРОСЕТИ ДЛЯ ПРЕПОДАВАТЕЛЯ"),
    (r"китайск.* нейрос",            "КИТАЙСКИЕ НЕЙРОСЕТИ"),
    (r"airtable",                    "AIRTABLE"),
    (r"tilda|тильд",                 "TILDA"),
    (r"ux.?ui",                      "UX/UI"),
    (r"веб[- ]?дизайн",              "ВЕБ-ДИЗАЙНЕР"),
    (r"python|пайтон|питон",         "ПРОГРАММИСТ НА PYTHON С CHATGPT"),
    (r"нейросет",                    "НЕЙРОСЕТИ: ОТ ПРИНЦИПОВ К ПРАКТИКЕ"),
]


def parse_gc_date(s):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").date().isoformat()
    except Exception:
        return s.strip()[:10]


def normalize_web_date(s):
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return s


def detect_external_source(source_page):
    sp = (source_page or "").lower()
    if "yandex" in sp or "яндекс" in sp:
        return "yandex"
    if "2gis" in sp or "2гис" in sp:
        return "2gis"
    if "irecommend" in sp:
        return "irecommend"
    if "google" in sp:
        return "google"
    if "tutortop" in sp:
        return "tutortop"
    if "okursah" in sp:
        return "okursah"
    if "skill2go" in sp:
        return "skill2go"
    if "kurshub" in sp:
        return "kurshub"
    if "pgdv" in sp:
        return "pgdv"
    return "external"


def match_course_by_keywords(text):
    t = (text or "").lower()
    for pat, course in KEYWORD_TO_COURSE:
        if re.search(pat, t):
            return course
    return "unknown"


def course_from_otzovik_page(source_page):
    sp = (source_page or "")
    if not sp:
        return "unknown"
    return match_course_by_keywords(sp)


def read_gc():
    """Идём по каждому курсу. В каждом файле рядом идут сообщения студентов
    и ответы куратора (одна и та же Группа, Email = CURATOR_EMAIL).
    Привязываем ответ к ближайшему предыдущему отзыву той же группы.
    """
    rows = []
    for path in sorted(GC_DIR.glob("*.csv")):
        slug = path.stem.replace("-reviews", "")
        course = GC_COURSE_MAP.get(slug, slug)
        with open(path, encoding="utf-8") as f:
            raw = list(csv.DictReader(f))
        # Сортируем по дате внутри группы — внутри файла данные уже в хроно,
        # но подстраховываемся.
        raw.sort(key=lambda r: (r.get("Группа") or "", r.get("Создан") or ""))

        # last_student_idx_by_group: индекс последнего «отзыва» в той же группе.
        last_by_group = {}
        # Сначала сложим студенческие отзывы как кандидатов.
        prepared = []
        for r in raw:
            email = (r.get("Email") or "").strip().lower()
            text  = (r.get("Текст") or "").strip()
            group = (r.get("Группа") or "").strip()
            date  = parse_gc_date(r.get("Создан") or "")
            if email == CURATOR_EMAIL:
                # Это ответ куратора — клеим к последнему отзыву той же группы.
                idx = last_by_group.get(group)
                if idx is not None and not prepared[idx]["reply"]:
                    prepared[idx]["reply"] = text
                continue
            prepared.append({
                "source": "gc",
                "date": date,
                "name": email,        # имени нет, оставляем email
                "rating_5": "",
                "course": course,
                "text": text,
                "pros": "",
                "cons": "",
                "reply": "",
                "url": "",
            })
            last_by_group[group] = len(prepared) - 1
        rows.extend(prepared)
    return rows


def read_otzovik():
    path = WEB_DIR / "reviews-otzovik.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "source": "otzovik",
                "date": normalize_web_date(r.get("date")),
                "name": (r.get("name") or "").strip(),
                "rating_5": (r.get("rating") or "").strip(),
                "course": course_from_otzovik_page(r.get("source_page")),
                "text": (r.get("text") or "").strip(),
                "pros": (r.get("pros") or "").strip(),
                "cons": (r.get("cons") or "").strip(),
                "reply": "",
                "url": (r.get("url") or "").strip(),
            })
    return rows


def read_external():
    path = WEB_DIR / "reviews-external.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            src = detect_external_source(r.get("source_page"))
            text = (r.get("text") or "").strip()
            rows.append({
                "source": src,
                "date": normalize_web_date(r.get("date")),
                "name": (r.get("name") or "").strip(),
                "rating_5": (r.get("rating") or "").strip(),
                "course": match_course_by_keywords(text),
                "text": text,
                "pros": "",
                "cons": "",
                "reply": "",
                "url": (r.get("url") or "").strip(),
            })
    return rows


def read_google():
    path = WEB_DIR / "reviews-google.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            text = (r.get("text") or "").strip()
            rows.append({
                "source": "google",
                "date": normalize_web_date(r.get("date")),
                "name": (r.get("name") or "").strip(),
                "rating_5": (r.get("rating") or "").strip(),
                "course": match_course_by_keywords(text),
                "text": text,
                "pros": "",
                "cons": "",
                "reply": "",
                "url": (r.get("url") or "").strip(),
            })
    return rows


def main():
    all_rows = []
    all_rows += read_gc()
    all_rows += read_otzovik()
    all_rows += read_external()
    all_rows += read_google()

    # Сортировка: новые сверху.
    all_rows.sort(key=lambda r: r["date"] or "", reverse=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    # Сводка
    from collections import Counter
    by_src = Counter(r["source"] for r in all_rows)
    with_reply = sum(1 for r in all_rows if r["reply"])
    print(f"Total rows: {len(all_rows)}")
    print(f"With reply: {with_reply}")
    for src, n in by_src.most_common():
        print(f"  {src}: {n}")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
