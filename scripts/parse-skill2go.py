"""Парсер отзывов skill2go.com для Zerocoder.

Источник: https://skill2go.com/ru/a/zerocoder/
- Карточки `.card[id^="#review-item"]` внутри `.reviews`.
- 20 на первичной странице, докачка кнопкой "Показать еще" (AJAX, без URL-пагинации).
- Парсинг: Playwright → click "Показать еще" → bs4.

Выход: data/WebReviews/reviews-skill2go.{csv,json}
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

URL = "https://skill2go.com/ru/a/zerocoder/"
SOURCE_PAGE = "skill2go: Zerocoder"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']


def click_until_all_loaded(page, max_clicks=20):
    prev = 0
    stuck = 0
    for _ in range(max_clicks):
        n = page.locator('.card[id^="#review-item"]').count()
        print(f"  карточек: {n}")
        if n == prev:
            stuck += 1
            if stuck >= 2:
                break
        else:
            stuck = 0
        prev = n
        btn = page.locator('a', has_text='Показать еще').first
        if btn.count() == 0:
            print("  кнопки 'Показать еще' нет")
            break
        try:
            btn.scroll_into_view_if_needed(timeout=3000)
            btn.click(timeout=5000)
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  не кликается: {e}")
            break


def parse_date(s):
    """02.12.2021 -> 2021-12-02"""
    m = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', s.strip())
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return s.strip()


def parse_card(card):
    rid = (card.get('id') or '').lstrip('#')
    # имя — в card-header
    name_el = card.select_one('.card-header div > div, .card-header .name, .card-header')
    name = ''
    if name_el:
        # берём первую непустую строку текста заголовка
        for line in name_el.get_text(separator='\n').split('\n'):
            line = line.strip()
            if line and len(line) < 80 and not re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', line):
                name = line
                break

    body = card.select_one('.card-body')
    body_text = body.get_text(separator='\n').strip() if body else ''

    # rating: число "5.0" в начале body
    rating = None
    m_r = re.match(r'\s*(\d+(?:[.,]\d+)?)', body_text)
    if m_r:
        try:
            val = float(m_r.group(1).replace(',', '.'))
            rating = int(val) if val == int(val) else val
        except ValueError:
            pass

    # date: DD.MM.YYYY
    date = ''
    m_d = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', body_text)
    if m_d:
        date = parse_date(m_d.group(1))

    # Разрежем body по строкам, выделим title и text
    lines = [ln.strip() for ln in body_text.split('\n') if ln.strip()]
    # пропустим строки с рейтингом и датой
    content = [ln for ln in lines
               if not re.fullmatch(r'\d+(?:[.,]\d+)?', ln)
               and not re.fullmatch(r'\d{1,2}\.\d{1,2}\.\d{4}', ln)]
    title = content[0] if content else ''
    text = '\n'.join(content[1:]).strip() if len(content) > 1 else ''
    # если первая строка очень длинная — это сам текст, заголовка нет
    if len(title) > 200 and not text:
        text = title
        title = ''
    # "Еще" — артефакт сворачивания
    text = re.sub(r'\n?\s*Еще\s*$', '', text).strip()

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': title,
        'text': text,
        'pros': '',
        'cons': '',
        'reply': '',
        'url': f"{URL}#{rid}" if rid else URL,
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
        page.wait_for_load_state('domcontentloaded', timeout=30000)
        time.sleep(3)
        click_until_all_loaded(page)
        html = page.content()
        TMP_DIR.mkdir(exist_ok=True)
        (TMP_DIR / "skill2go-final.html").write_text(html, encoding='utf-8')
        browser.close()
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.card[id^="#review-item"]')
    print(f"\nИтоговых карточек: {len(cards)}")
    return [parse_card(c) for c in cards]


def save_all(reviews):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'reviews-skill2go.csv').write_text('', encoding='utf-8')
    csv_path = OUT_DIR / 'reviews-skill2go.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-skill2go.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")


def main():
    print("Парсер skill2go -> reviews-skill2go.{csv,json}")
    print("=" * 50)
    reviews = scrape()
    # дедупликация по url (содержит #review-itemNNN)
    seen = set()
    unique = []
    for r in reviews:
        if r['url'] in seen:
            continue
        seen.add(r['url'])
        unique.append(r)
    reviews = unique
    print(f"Уникальных (после дедупа по id): {len(reviews)}")
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    save_all(reviews)
    rated = [r for r in reviews if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    print(f"\nСтатистика:")
    print(f"  С текстом: {sum(1 for r in reviews if r.get('text'))}/{len(reviews)}")
    print(f"  Средний рейтинг: {avg:.2f}")
    if reviews:
        print(f"\nПервые 3:")
        for r in reviews[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {r['title'][:60]}")


if __name__ == '__main__':
    main()
