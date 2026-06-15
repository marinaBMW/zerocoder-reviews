"""Парсер отзывов okursah.ru для Zerocoder.

Источник: https://okursah.ru/s/zerocoder/reviews
- На странице первичный листинг 30 карточек.
- Доп. отзывы подгружаются кнопкой "Показать еще" (Alpine.js, AJAX).
- Парсинг через Playwright: клик до конца, затем bs4 на финальном DOM.

Выход: data/WebReviews/reviews-okursah.{csv,json}
Схема: date, name, rating, title, text, pros, cons, reply, url, source_page
"""
import csv
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "WebReviews"
TMP_DIR = PROJECT_ROOT / "tmp"

URL = "https://okursah.ru/s/zerocoder/reviews"
SOURCE_PAGE = 'okursah.ru: ZEROCODER'
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']


def click_until_all_loaded(page, max_clicks=20):
    """Кликает 'Показать еще', пока кнопка не исчезнет или не перестанет добавлять отзывы."""
    prev_count = 0
    stuck = 0
    for i in range(max_clicks):
        cards = page.locator('[itemtype*="Review"]').count()
        print(f"  карточек на странице: {cards}")
        if cards == prev_count:
            stuck += 1
            if stuck >= 2:
                print("  кол-во не растёт, выходим")
                break
        else:
            stuck = 0
        prev_count = cards
        # Попробуем найти кнопку «Показать еще»
        btn = page.locator('button', has_text='Показать еще')
        if btn.count() == 0:
            print("  кнопки 'Показать еще' нет, конец")
            break
        try:
            btn.first.scroll_into_view_if_needed(timeout=3000)
            btn.first.click(timeout=5000)
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  клик не сработал: {e}")
            break


def parse_card(card):
    name = card.select_one('[itemprop="author"] [itemprop="name"]')
    name = name.get_text(strip=True) if name else ''

    dt = card.select_one('time[itemprop="datePublished"]')
    date_iso = dt.get('datetime', '') if dt else ''
    # 2025-11-06T21:00:00.000000Z -> 2025-11-06
    date = date_iso[:10] if len(date_iso) >= 10 else ''

    rating_meta = card.select_one('meta[itemprop="ratingValue"]')
    rating = None
    if rating_meta:
        try:
            rating = int(float(rating_meta.get('content', '0')))
        except ValueError:
            rating = None

    body = card.select_one('[itemprop="reviewBody"], [itemprop="description"]')
    text = body.get_text(separator='\n').strip() if body else ''

    # Заголовок отзыва — на okursah обычно есть короткий заголовок над текстом.
    # Часто верстается жирным текстом сразу после имени/даты.
    # Берём первый h2/h3/h4 внутри карточки.
    title_el = card.select_one('h2, h3, h4')
    title = title_el.get_text(strip=True) if title_el else ''
    # Если заголовок совпадает с именем автора — отбросим
    if title == name:
        title = ''

    # Если description пустой — пробуем достать всё видимое
    if not text:
        text = card.get_text(separator='\n').strip()
        # уберём шапку (имя, дата, заголовок)
        for skip in [name, title]:
            if skip and skip in text:
                idx = text.find(skip) + len(skip)
                text = text[idx:].lstrip()

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': title,
        'text': text,
        'pros': '',
        'cons': '',
        'reply': '',  # на okursah ответов школы в карточке не видно
        'url': URL,
        'source_page': SOURCE_PAGE,
    }


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='ru-RU',
            viewport={'width': 1366, 'height': 900},
        )
        page = context.new_page()
        print(f"Открываю {URL}")
        page.goto(URL, timeout=60000)
        page.wait_for_load_state('networkidle', timeout=15000)
        time.sleep(2)
        click_until_all_loaded(page)
        html = page.content()
        TMP_DIR.mkdir(exist_ok=True)
        (TMP_DIR / "okursah-final.html").write_text(html, encoding='utf-8')
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('[itemtype*="Review"]')
    print(f"\nИтоговых карточек: {len(cards)}")
    reviews = [parse_card(c) for c in cards]
    return reviews


def save_all(reviews):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-okursah.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-okursah.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")


def main():
    print("Парсер okursah.ru -> reviews-okursah.{csv,json}")
    print("=" * 50)
    reviews = scrape()
    # дедупликация по (name, date, первые 60 символов текста)
    seen = set()
    out = []
    for r in reviews:
        key = (r['name'], r['date'], (r['text'] or '')[:60])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    out.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    save_all(out)
    rated = [r for r in out if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    print(f"\nСтатистика:")
    print(f"  С текстом: {sum(1 for r in out if r.get('text'))}/{len(out)}")
    print(f"  Средний рейтинг: {avg:.2f}")
    if out:
        print(f"\nПервые 3:")
        for r in out[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {r['title'][:60]}")


if __name__ == '__main__':
    main()
