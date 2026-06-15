"""Интерактивный парсер iRecommend для Zerocoder.

Источник: https://irecommend.ru/content/sait-zerokoder-0
- Пазл-капча на старте и периодически. Решает Маришка в открытом окне Chromium.
- Листинг — 12 отзывов (превью + ссылки на полные страницы).
- Полный текст — на отдельной странице каждого отзыва.

Схема:
- Открываем Chromium в headless=False.
- Каждый goto проверяется на капчу. При капче ставится файл-флаг
  tmp/irecommend-captcha-pending.txt и скрипт ждёт его удаления
  (Клод убирает по команде Маришки «решила»).
- Cookies сохраняются в tmp/irecommend-storage.json, чтобы повторные запуски
  стартовали без капчи.

Выход: data/WebReviews/reviews-irecommend.{csv,json}
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
STORAGE = TMP_DIR / "irecommend-storage.json"
CAPTCHA_FLAG = TMP_DIR / "irecommend-captcha-pending.txt"

LISTING_URL = "https://irecommend.ru/content/sait-zerokoder-0"
SOURCE_PAGE = "iRecommend: Сайт Зерокодер"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']

DEEP_DELAY_SEC = 5  # пауза между отдельными отзывами

MONTHS_NUM = {}  # не нужно — даты в формате DD.MM.YYYY


def is_captcha(html, title=''):
    if 'Вы точно не робот' in (html or ''):
        return True
    if title == 'Irecommend' and 'sait-zerokoder' not in (html or '').lower():
        return True
    return False


def wait_for_captcha_solved(page, url, label=''):
    page.goto(url, timeout=60000)
    page.wait_for_load_state('domcontentloaded')
    time.sleep(2)
    while True:
        html = page.content()
        title = page.title()
        if not is_captcha(html, title):
            return html
        print(f"\n  [!] Капча на {label or url}", flush=True)
        print("      Реши пазл в окне Chromium и скажи Клоду 'решила'.", flush=True)
        TMP_DIR.mkdir(exist_ok=True)
        CAPTCHA_FLAG.write_text(f"captcha at {url}", encoding='utf-8')
        while CAPTCHA_FLAG.exists():
            time.sleep(2)
        print("      [ok] флаг снят, продолжаю", flush=True)
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)
        except Exception as e:
            print(f"      ошибка перезагрузки: {e}")
            time.sleep(3)


def parse_listing(html):
    """Извлекает 12 карточек листинга: name, date, title, url."""
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('ul.list-comments > li.item')
    out = []
    for li in items:
        link = li.select_one('a.reviewTextSnippet')
        href = link.get('href') if link else ''
        if href and href.startswith('/'):
            href = 'https://irecommend.ru' + href
        name_el = li.select_one('.authorName a')
        date_el = li.select_one('.created')
        title_el = li.select_one('.reviewTitle')
        teaser_el = li.select_one('.reviewTeaserText')
        date = ''
        if date_el:
            d = date_el.get_text(strip=True)
            m = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', d)
            if m:
                date = f"{m.group(3)}-{m.group(2):0>2}-{m.group(1):0>2}"
        out.append({
            'url': href,
            'name': name_el.get_text(strip=True) if name_el else '',
            'date': date,
            'title': title_el.get_text(strip=True) if title_el else '',
            'teaser': teaser_el.get_text(separator='\n').strip() if teaser_el else '',
        })
    return out


def parse_review_page(html):
    """Парсит страницу отдельного отзыва: rating, полный текст, reply."""
    soup = BeautifulSoup(html, 'html.parser')
    out = {'rating': None, 'text': '', 'reply': ''}
    # рейтинг через микроразметку
    rv = soup.select_one('[itemprop="ratingValue"]')
    if rv:
        content = rv.get('content') or rv.get_text(strip=True)
        try:
            out['rating'] = int(float(content))
        except (ValueError, TypeError):
            pass
    # текст
    body = soup.select_one('[itemprop="reviewBody"], .reviewText')
    if body:
        out['text'] = body.get_text(separator='\n').strip()
    # ответ представителя — ищем блок с пометкой об ответе owner/admin
    # iRecommend обычно показывает комментарии в .comment / .comments
    for c in soup.select('.comment'):
        author = c.select_one('.username, .author')
        if author and re.search(r'zerocoder|зерокодер|представитель|owner', author.get_text(), re.I):
            txt = c.get_text(separator='\n').strip()
            out['reply'] = txt
            break
    return out


def main():
    print("Парсер iRecommend (интерактивный) -> reviews-irecommend.{csv,json}")
    print("=" * 50)
    TMP_DIR.mkdir(exist_ok=True)
    # сразу подчистим флаг — на случай мусора
    if CAPTCHA_FLAG.exists():
        CAPTCHA_FLAG.unlink()

    storage_arg = {}
    if STORAGE.exists():
        print(f"Подхватываю cookies из {STORAGE.name}")
        storage_arg = {'storage_state': str(STORAGE)}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='ru-RU',
            viewport={'width': 1366, 'height': 900},
            **storage_arg,
        )
        page = context.new_page()

        # Этап 1: листинг
        print(f"\n[1/2] Листинг: {LISTING_URL}")
        html = wait_for_captcha_solved(page, LISTING_URL, label="листинг")
        items = parse_listing(html)
        print(f"  Найдено карточек: {len(items)}")
        try:
            context.storage_state(path=str(STORAGE))
        except Exception:
            pass

        # Этап 2: deep-fetch
        print(f"\n[2/2] Deep-fetch (12 страниц, пауза {DEEP_DELAY_SEC}s)")
        for i, it in enumerate(items, 1):
            url = it['url']
            if not url:
                continue
            print(f"  [{i}/{len(items)}] {url}")
            try:
                html = wait_for_captcha_solved(page, url, label=url)
                time.sleep(DEEP_DELAY_SEC)
            except Exception as e:
                print(f"    ошибка: {e}")
                continue
            deep = parse_review_page(html)
            it['rating'] = deep.get('rating')
            # если deep дал полный текст — используем его, иначе teaser
            it['text'] = deep.get('text') or it.get('teaser', '')
            it['reply'] = deep.get('reply', '')
            try:
                context.storage_state(path=str(STORAGE))
            except Exception:
                pass

        browser.close()

    # Собираем выход
    reviews = []
    for it in items:
        reviews.append({
            'date': it.get('date', ''),
            'name': it.get('name', ''),
            'rating': it.get('rating'),
            'title': it.get('title', ''),
            'text': it.get('text', ''),
            'pros': '',
            'cons': '',
            'reply': it.get('reply', ''),
            'url': it.get('url', ''),
            'source_page': SOURCE_PAGE,
        })
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-irecommend.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-irecommend.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")
    rated = [r for r in reviews if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    print(f"\nС текстом: {sum(1 for r in reviews if r.get('text'))}/{len(reviews)}")
    print(f"С ответом: {sum(1 for r in reviews if r.get('reply'))}/{len(reviews)}")
    print(f"Средний рейтинг: {avg:.2f}")
    if reviews:
        print("\nПервые 3:")
        for r in reviews[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {r['title'][:60]}")


if __name__ == '__main__':
    main()
