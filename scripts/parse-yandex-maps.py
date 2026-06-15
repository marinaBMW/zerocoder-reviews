"""Парсер отзывов Яндекс Карт для Zerocoder.

Источник: https://yandex.ru/maps/org/zerokoder/149083959380/reviews/
- SPA на React. Карточки .business-review-view, 21 шт.
- Текст и ответ организации обрезаются — нужно кликать «Ещё» и «Посмотреть ответ организации».

Стратегия:
- Playwright (headless).
- Скролл блока отзывов, чтобы все подгрузились.
- JS-клик всех expand-кнопок.
- Финальный DOM → bs4 → CSV/JSON.

Выход: data/WebReviews/reviews-yandex.{csv,json}
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

URL = "https://yandex.ru/maps/org/zerokoder/149083959380/reviews/"
SOURCE_PAGE = "Яндекс Карты: Зерокодер"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']


def scroll_until_all_loaded(page, max_iter=30):
    """Скроллит панель отзывов, пока количество карточек не перестанет расти."""
    prev = 0
    stuck = 0
    for _ in range(max_iter):
        n = page.locator('.business-review-view').count()
        print(f"  карточек: {n}")
        if n == prev:
            stuck += 1
            if stuck >= 3:
                break
        else:
            stuck = 0
        prev = n
        # Скролл внутри scrollable-области отзывов
        page.evaluate("""() => {
            const cards = document.querySelectorAll('.business-review-view');
            const last = cards[cards.length - 1];
            if (last) last.scrollIntoView({block: 'end'});
            // Также пробуем найти scrollable-родителя и скроллим его
            for (const c of cards) {
                let p = c.parentElement;
                while (p) {
                    const s = getComputedStyle(p);
                    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && p.scrollHeight > p.clientHeight) {
                        p.scrollTop = p.scrollHeight;
                        return;
                    }
                    p = p.parentElement;
                }
            }
        }""")
        page.wait_for_timeout(1200)


def expand_all(page):
    """Кликает все 'Ещё' (раскрытие текста) и 'Посмотреть ответ организации' через JS."""
    # Раскрытие текста
    page.evaluate("""() => {
        document.querySelectorAll('.business-review-view__expand').forEach(e => {
            try { e.click(); } catch(_) {}
        });
    }""")
    page.wait_for_timeout(1000)
    # Раскрытие ответов организации
    page.evaluate("""() => {
        document.querySelectorAll('.business-review-view__comment-expand').forEach(e => {
            try { e.click(); } catch(_) {}
        });
    }""")
    page.wait_for_timeout(2000)


def parse_iso_date(s):
    if not s:
        return ''
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ''


def parse_card(card):
    # Имя
    name_el = card.select_one('[itemprop="author"] [itemprop="name"]')
    name = name_el.get_text(strip=True) if name_el else ''
    # Дата (ISO в meta)
    date_meta = card.select_one('meta[itemprop="datePublished"]')
    date = parse_iso_date(date_meta.get('content', '') if date_meta else '')
    # Рейтинг
    rating_meta = card.select_one('meta[itemprop="ratingValue"]')
    rating = None
    if rating_meta:
        try:
            v = float(rating_meta.get('content', '0'))
            rating = int(v) if v == int(v) else v
        except ValueError:
            pass
    # Тело отзыва
    body_el = card.select_one('[itemprop="reviewBody"]')
    text = ''
    if body_el:
        # внутри spoiler-view__text-container с полным текстом
        container = body_el.select_one('.spoiler-view__text-container')
        if container:
            text = container.get_text(separator='\n').strip()
        else:
            text = body_el.get_text(separator='\n').strip()
        # уберём конечный "ещё" / "Ещё"
        text = re.sub(r'\n?\s*Ещё\s*$', '', text, flags=re.I).strip()

    # Ответ организации
    reply = ''
    reply_el = card.select_one('.business-review-comment-content__bubble')
    if reply_el:
        reply = reply_el.get_text(separator='\n').strip()
    if not reply:
        # запасной вариант — весь блок комментария без шапки
        comment = card.select_one('.business-review-comment-content')
        if comment:
            text_full = comment.get_text(separator='\n').strip()
            # отрежем шапку "Официальный ответ DD месяц"
            reply = re.sub(r'^Официальный ответ.*?\n', '', text_full, count=1, flags=re.S).strip()

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': '',
        'text': text,
        'pros': '',
        'cons': '',
        'reply': reply,
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
        page.wait_for_load_state('domcontentloaded', timeout=30000)
        time.sleep(4)
        scroll_until_all_loaded(page)
        time.sleep(2)
        expand_all(page)
        time.sleep(2)
        html = page.content()
        TMP_DIR.mkdir(exist_ok=True)
        (TMP_DIR / "yandex-final.html").write_text(html, encoding='utf-8')
        browser.close()
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.business-review-view')
    print(f"\nИтоговых карточек: {len(cards)}")
    return [parse_card(c) for c in cards]


def main():
    print("Парсер Яндекс Карты -> reviews-yandex.{csv,json}")
    print("=" * 50)
    reviews = scrape()
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-yandex.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-yandex.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")
    rated = [r for r in reviews if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    with_text = sum(1 for r in reviews if r.get('text'))
    with_reply = sum(1 for r in reviews if r.get('reply'))
    print(f"\nС текстом: {with_text}/{len(reviews)}")
    print(f"С ответом организации: {with_reply}/{len(reviews)}")
    print(f"Средний рейтинг: {avg:.2f}")
    if reviews:
        print("\nПервые 3:")
        for r in reviews[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {(r['text'] or '')[:60]}")


if __name__ == '__main__':
    main()
