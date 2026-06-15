import csv
import json
import time
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

DOMAIN = "https://otzovik.com"
PROJECT_ROOT = Path(__file__).parent.parent
WEBREVIEWS_DIR = PROJECT_ROOT / "data" / "WebReviews"
TMP_DIR = PROJECT_ROOT / "tmp"
PAGES_REGISTRY = WEBREVIEWS_DIR / "otzovik-pages.csv"

MONTHS_RU = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}

FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']
DEEP_CACHE = TMP_DIR / "otzovik-deep-cache.json"
DEEP_DELAY_SEC = 12          # пауза между запросами на странице отзыва
CAPTCHA_COOLDOWN_SEC = 120   # пауза, если поймали капчу
CAPTCHA_MAX_RETRIES = 2      # столько раз пробуем повторно после капчи
CAPTCHA_HALT_AFTER = 5       # если 5 капч подряд — стоп, чтобы не получить бан


def load_pages_registry():
    with open(PAGES_REGISTRY, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def parse_date(date_str):
    date_str = date_str.strip()
    match = re.match(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
    if match:
        d, month_str, y = match.groups()
        m = MONTHS_RU.get(month_str.lower()[:3])
        if m:
            return datetime(int(y), m, int(d))
    return None


def get_total_pages(soup):
    pages = []
    for a in soup.select('.pager a, .pagination a, [class*="pager"] a'):
        try:
            pages.append(int(a.get_text(strip=True)))
        except ValueError:
            pass
        href = a.get('href', '')
        m = re.search(r'/(\d+)/$', href)
        if m:
            pages.append(int(m.group(1)))
    return max(pages) if pages else 1


def detect_review_selector(soup):
    candidates = [
        '.review-item',
        'div.item',
        '[class*="review-item"]',
        '[itemtype*="Review"]',
        'article',
    ]
    for sel in candidates:
        items = soup.select(sel)
        if len(items) >= 3:
            sample_text = items[0].get_text(strip=True)
            if len(sample_text) > 50:
                return sel, items
    return None, []


def parse_reviews_from_html(html, source_url, source_page_title):
    soup = BeautifulSoup(html, 'html.parser')
    reviews = []

    _, items = detect_review_selector(soup)
    if not items:
        return reviews

    for item in items:
        name_el = item.select_one('[itemprop="author"] .user-login')
        if not name_el:
            name_el = item.select_one('[itemprop="author"] a[href*="/profile/"]')
        name = name_el.get_text(strip=True) if name_el else ''

        rating = None
        for el in item.select('[class*="rating"], [class*="grade"], [class*="score"]'):
            text = el.get_text(strip=True)
            m = re.search(r'^(\d)$', text)
            if m and 1 <= int(m.group(1)) <= 5:
                rating = int(m.group(1))
                break
        if rating is None:
            filled = item.select('[class*="fill"], [class*="active"], [class*="on"]')
            if 1 <= len(filled) <= 5:
                rating = len(filled)

        date_str = ''
        all_text = item.get_text(separator=' ')
        date_match = re.search(
            r'\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\w*\s+\d{4}', all_text, re.I
        )
        if date_match:
            date_str = date_match.group(0)
        date_obj = parse_date(date_str)
        date_formatted = date_obj.strftime('%Y-%m-%d') if date_obj else date_str

        title_el = item.select_one('h3 a, h2 a, [class*="title"] a, [class*="header"] a')
        title = title_el.get_text(strip=True) if title_el else ''

        href = title_el.get('href', '') if title_el else ''
        review_url = DOMAIN + href if href.startswith('/') else href or source_url

        teaser_el = item.select_one('[itemprop="description"], .review-teaser')
        text = teaser_el.get_text(strip=True) if teaser_el else ''

        pros_el = item.select_one('[class*="plus"], [class*="pro"], [class*="advantage"], [class*="good"]')
        pros = ''
        if pros_el:
            pros = pros_el.get_text(strip=True)
            pros = re.sub(r'^(Достоинства|Плюсы)\s*:?\s*', '', pros, flags=re.I).strip()

        cons_el = item.select_one('[class*="minus"], [class*="con"], [class*="disadvantage"], [class*="bad"]')
        cons = ''
        if cons_el:
            cons = cons_el.get_text(strip=True)
            cons = re.sub(r'^(Недостатки|Минусы)\s*:?\s*', '', cons, flags=re.I).strip()

        if not name and not title:
            continue

        reviews.append({
            'date': date_formatted,
            'name': name,
            'rating': rating,
            'title': title,
            'text': text,
            'pros': pros,
            'cons': cons,
            'reply': '',
            'url': review_url,
            'source_page': source_page_title,
        })

    return reviews


def parse_review_page(html):
    """Парсит индивидуальную страницу отзыва.
    Возвращает dict с полным текстом, pros, cons и reply (ответом представителя).
    """
    soup = BeautifulSoup(html, 'html.parser')
    out = {'text': '', 'pros': '', 'cons': '', 'reply': ''}

    body = soup.select_one('.review-body.description, .review-body, [itemprop="reviewBody"]')
    if body:
        out['text'] = body.get_text(separator='\n').strip()

    pros_el = soup.select_one('.review-plus')
    if pros_el:
        s = pros_el.get_text(separator=' ').strip()
        out['pros'] = re.sub(r'^(Достоинства|Плюсы)\s*:?\s*', '', s, flags=re.I).strip()

    cons_el = soup.select_one('.review-minus')
    if cons_el:
        s = cons_el.get_text(separator=' ').strip()
        out['cons'] = re.sub(r'^(Недостатки|Минусы)\s*:?\s*', '', s, flags=re.I).strip()

    # Ответ официального представителя — все .comment.official, склеенные через \n\n
    official_comments = soup.select('.comment.official, .comment-official, [class*="comment"][class*="official"]')
    if official_comments:
        replies = []
        for c in official_comments:
            txt = c.get_text(separator='\n').strip()
            # уберём служебные строки «Ответить», «Оставить свой комментарий»
            cleaned = []
            for line in txt.split('\n'):
                line = line.strip()
                if not line or line in ('Ответить', 'Оставить свой комментарий', 'Официальный представитель'):
                    continue
                cleaned.append(line)
            replies.append('\n'.join(cleaned))
        out['reply'] = '\n\n---\n\n'.join(replies).strip()

    return out


def load_deep_cache():
    if DEEP_CACHE.exists():
        with open(DEEP_CACHE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_deep_cache(cache):
    DEEP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEEP_CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def is_captcha(html, page_title=""):
    """Отзовик защищает страницы капчей. Признаки:
    - в title написано «Вы робот?»
    - в URL появляется параметр capt4a
    - страница содержит «Чтобы продолжить, докажите»
    """
    if "Вы робот" in (page_title or ""):
        return True
    if "capt4a" in (html or ""):
        return True
    if "докажите, что вы не робот" in (html or "").lower():
        return True
    return False


def fetch_review_page(page, url):
    """Загружает страницу отзыва, обрабатывает капчу.
    Возвращает (data, status), где status: 'ok' | 'captcha' | 'fail'
    """
    for attempt in range(CAPTCHA_MAX_RETRIES + 1):
        try:
            page.goto(url, timeout=30000)
            time.sleep(DEEP_DELAY_SEC)
            html = page.content()
            title = page.title()
        except Exception as e:
            return None, 'fail'

        if is_captcha(html, title):
            if attempt < CAPTCHA_MAX_RETRIES:
                print(f"    капча на {url}, ждём {CAPTCHA_COOLDOWN_SEC}s...")
                time.sleep(CAPTCHA_COOLDOWN_SEC)
                continue
            return None, 'captcha'

        data = parse_review_page(html)
        # если парсер не нашёл ничего — относимся как к капче (могла быть промежуточная страница)
        if not data.get('text') and not data.get('pros') and not data.get('cons'):
            return None, 'captcha'
        return data, 'ok'

    return None, 'captcha'


def enrich_with_deep(reviews, page, limit=None):
    """Дозабирает полный текст + reply со страницы каждого отзыва.
    Кэширует по URL в tmp/otzovik-deep-cache.json — устойчиво к прерываниям.
    Пустые/капча-ответы НЕ кэшируем, чтобы при следующем запуске попробовать заново.
    """
    cache = load_deep_cache()
    print(f"\nDeep-enrich: всего {len(reviews)} отзывов, в кэше {len(cache)}")
    print(f"  пауза: {DEEP_DELAY_SEC}s/req · cooldown капчи: {CAPTCHA_COOLDOWN_SEC}s · стоп после {CAPTCHA_HALT_AFTER} капч подряд")
    processed = 0
    captcha_streak = 0
    save_every = 25
    for i, r in enumerate(reviews):
        if limit is not None and processed >= limit:
            break
        url = r.get('url') or ''
        if not url.startswith('http'):
            continue
        if url in cache:
            data = cache[url]
        else:
            data, status = fetch_review_page(page, url)
            if status == 'ok':
                cache[url] = data
                processed += 1
                captcha_streak = 0
                if processed % 5 == 0:
                    print(f"  ok: {processed} новых, всего в кэше {len(cache)}, осталось {len(reviews) - i - 1}")
                if processed % save_every == 0:
                    save_deep_cache(cache)
            elif status == 'captcha':
                captcha_streak += 1
                print(f"  капча {captcha_streak}/{CAPTCHA_HALT_AFTER} ({url})")
                if captcha_streak >= CAPTCHA_HALT_AFTER:
                    print(f"\n  СТОП: {CAPTCHA_HALT_AFTER} капч подряд. Сохраняю кэш и выхожу.")
                    save_deep_cache(cache)
                    return
                continue
            else:
                print(f"  fail {url}")
                continue
        # обогащаем запись (только если data есть)
        if data:
            if data.get('text'):  r['text']  = data['text']
            if data.get('pros'):  r['pros']  = data['pros']
            if data.get('cons'):  r['cons']  = data['cons']
            if data.get('reply'): r['reply'] = data['reply']
    save_deep_cache(cache)
    print(f"Deep-enrich завершён. Новых обработано: {processed}, в кэше: {len(cache)}")


def scrape_card(page, slug, title, start_url):
    all_reviews = []

    print(f"\n  [{slug}] {title}")
    print(f"  URL: {start_url}")
    page.goto(start_url, timeout=30000)
    time.sleep(3)

    html = page.content()

    TMP_DIR.mkdir(exist_ok=True)
    debug_path = TMP_DIR / f"otzovik-{slug}.html"
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(html)

    soup = BeautifulSoup(html, 'html.parser')
    total_pages = get_total_pages(soup)
    print(f"  Страниц: {total_pages}")

    reviews = parse_reviews_from_html(html, start_url, title)
    all_reviews.extend(reviews)
    print(f"  Стр. 1: {len(reviews)} отзывов")

    for page_num in range(2, total_pages + 1):
        time.sleep(4)
        page_url = f"{start_url}{page_num}/"
        try:
            page.goto(page_url, timeout=30000)
            time.sleep(4)
            html = page.content()
            reviews = parse_reviews_from_html(html, page_url, title)
            all_reviews.extend(reviews)
            print(f"  Стр. {page_num}: {len(reviews)} отзывов")
        except Exception as e:
            print(f"  Стр. {page_num}: ошибка — {e}")

    return all_reviews


def deduplicate(reviews):
    seen = set()
    unique = []
    for r in reviews:
        key = (r['name'], r['date'], r['title'][:50], r['source_page'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def save_all(reviews):
    WEBREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = WEBREVIEWS_DIR / 'reviews-otzovik.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(reviews)

    json_path = WEBREVIEWS_DIR / 'reviews-otzovik.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

    print(f"\n  Записано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")


def main():
    pages = load_pages_registry()
    print(f"Карточек в реестре: {len(pages)}")
    print("=" * 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='ru-RU',
            viewport={'width': 1366, 'height': 900},
        )
        page = context.new_page()

        all_reviews = []
        for i, p_row in enumerate(pages, 1):
            print(f"\n[{i}/{len(pages)}]")
            try:
                reviews = scrape_card(page, p_row['slug'], p_row['title'], p_row['url'])
                all_reviews.extend(reviews)
                print(f"  Итого с карточки: {len(reviews)}")
            except Exception as e:
                print(f"  ОШИБКА на карточке {p_row['slug']}: {e}")
            time.sleep(6)

        # Этап 2: deep-fetch (полный текст + ответ представителя)
        print("\n" + "=" * 50)
        print("Этап 2: deep-fetch отдельных страниц отзывов")
        print("=" * 50)
        combined = deduplicate(all_reviews)
        combined.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00', reverse=True)
        enrich_with_deep(combined, page)

        browser.close()

    print("\nОбъединяю и дедуплицирую...")
    combined.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00', reverse=True)

    save_all(combined)

    print(f"\nВсего уникальных отзывов: {len(combined)}")
    print("\nПервые 3:")
    for r in combined[:3]:
        print(f"  [{r['date']}] {r['name']} — {r['rating']}★ — {r['source_page'][:50]}")


if __name__ == '__main__':
    main()
