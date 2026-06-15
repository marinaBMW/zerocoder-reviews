"""Парсер отзывов pgdv.ru для Zerocoder.

Источник: https://pgdv.ru/reviews/zerocoder-otzyvy
- Карточки `.ec-message` (28 шт, многие — дубликаты).
- Рейтинг: `.ec-stars span.rating-N` (N = 1..5).
- HTML без JS.

Выход: data/WebReviews/reviews-pgdv.{csv,json}
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

URL = "https://pgdv.ru/reviews/zerocoder-otzyvy"
SOURCE_PAGE = "pgdv.ru: ZEROCODER"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}


def parse_card(msg):
    rid = msg.get('id', '').replace('ec-resource-1732-message-', '')
    name_el = msg.select_one('.ec-message__author')
    name = name_el.get_text(strip=True) if name_el else ''
    date_el = msg.select_one('.ec-message__date')
    date_raw = date_el.get_text(strip=True) if date_el else ''
    # "2022-11-13 20:30:11" -> "2022-11-13"
    m = re.match(r'(\d{4}-\d{2}-\d{2})', date_raw)
    date = m.group(1) if m else ''

    # Рейтинг через .ec-stars span с классом rating-N
    rating = None
    star = msg.select_one('.ec-stars span[class^="rating-"]')
    if star:
        cls = ' '.join(star.get('class') or [])
        m_r = re.search(r'rating-(\d+)', cls)
        if m_r:
            rating = int(m_r.group(1))

    # Заголовок и текст — внутри <p> после .ec-stars
    title = ''
    text = ''
    p = msg.select_one('p')
    if p:
        # заменим <br> на \n
        for br in p.find_all('br'):
            br.replace_with('\n')
        full = p.get_text(separator='\n').strip()
        lines = [ln.strip() for ln in full.split('\n') if ln.strip()]
        if lines:
            title = lines[0]
            text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
            # если title длинный — это весь отзыв
            if not text and len(title) > 200:
                text = title
                title = ''

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': title,
        'text': text,
        'pros': '',
        'cons': '',
        'reply': '',
        'url': f"{URL}#message-{rid}" if rid else URL,
        'source_page': SOURCE_PAGE,
    }


def main():
    print("Парсер pgdv.ru -> reviews-pgdv.{csv,json}")
    print("=" * 50)
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    TMP_DIR.mkdir(exist_ok=True)
    (TMP_DIR / "pgdv-page.html").write_text(r.text, encoding='utf-8')
    soup = BeautifulSoup(r.text, 'html.parser')
    cards = soup.select('.ec-message')
    print(f"Карточек на странице: {len(cards)}")
    raw = [parse_card(c) for c in cards]

    # Дедупликация по (name, text first 200 chars). Сохраняем лучшее: с самой ранней датой.
    seen = {}
    for r in raw:
        key = (r['name'], (r['text'] or r['title'])[:200])
        if key not in seen:
            seen[key] = r
        else:
            # выберем тот, у кого корректнее заполнены поля (с большим title+text)
            cur = seen[key]
            if len((r['title'] or '') + (r['text'] or '')) > len((cur['title'] or '') + (cur['text'] or '')):
                seen[key] = r
    reviews = sorted(seen.values(), key=lambda r: r.get('date') or '0000-00-00', reverse=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-pgdv.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-pgdv.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} уникальных отзывов (из {len(raw)} сырых)")
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
