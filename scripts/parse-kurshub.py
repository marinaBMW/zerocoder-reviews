"""Парсер отзывов kurshub.ru для Zerocoder.

Источник: https://kurshub.ru/reviews/zerocoder-ru/
- Карточки `.review__item[data-id]`, с data-атрибутами data-review_date (YYYYMMDD), data-rating.
- На странице ~10 отзывов, пагинации нет (в title 34 — устаревшая мета).
- HTML отдаётся curl'ом без JS.

Выход: data/WebReviews/reviews-kurshub.{csv,json}
Схема: date, name, rating, title, text, pros, cons, reply, url, source_page
"""
import csv
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "WebReviews"
TMP_DIR = PROJECT_ROOT / "tmp"

URL = "https://kurshub.ru/reviews/zerocoder-ru/"
SOURCE_PAGE = "KursHub: ZeroCoder"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}


def parse_yyyymmdd(s):
    s = (s or '').strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return ''


def parse_card(card):
    rid = card.get('data-id', '') or (card.get('id') or '').lstrip('id')
    date = parse_yyyymmdd(card.get('data-review_date'))
    try:
        rating = int(card.get('data-rating') or 0) or None
    except ValueError:
        rating = None

    title_el = card.select_one('h2')
    title = title_el.get_text(' ', strip=True) if title_el else ''
    # Удалим якорь-tooltip из заголовка, если есть
    title = re.sub(r'\s+$', '', title)

    text_el = card.select_one('.text .inner, .text')
    text = text_el.get_text(separator='\n').strip() if text_el else ''

    name_el = card.select_one('.bottom .name')
    name = name_el.get_text(strip=True) if name_el else ''

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': title,
        'text': text,
        'pros': '',
        'cons': '',
        'reply': '',
        'url': f"{URL}#id{rid}" if rid else URL,
        'source_page': SOURCE_PAGE,
    }


def main():
    print("Парсер kurshub.ru -> reviews-kurshub.{csv,json}")
    print("=" * 50)
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    TMP_DIR.mkdir(exist_ok=True)
    (TMP_DIR / "kurshub-page.html").write_text(r.text, encoding='utf-8')
    soup = BeautifulSoup(r.text, 'html.parser')
    cards = soup.select('.review__item[data-id]')
    print(f"Карточек на странице: {len(cards)}")
    reviews = [parse_card(c) for c in cards]
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-kurshub.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-kurshub.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")
    rated = [r for r in reviews if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    print(f"\nС текстом: {sum(1 for r in reviews if r.get('text'))}/{len(reviews)}")
    print(f"Средний рейтинг: {avg:.2f}")
    if reviews:
        print("\nПервые 3:")
        for r in reviews[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {r['title'][:60]}")


if __name__ == '__main__':
    main()
