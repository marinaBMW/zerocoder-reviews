"""Интерактивный парсер Отзовика для случая, когда IP под капчей.

Чем отличается от parse-otzovik.py:
- Открывает Chromium в видимом режиме (headless=False).
- При капче ставит парсер на паузу и просит Маришку решить капчу в окне.
- Сохраняет cookies в tmp/otzovik-storage.json — следующий запуск, скорее всего,
  стартует уже без капчи.
- Использует тот же кэш отзывов tmp/otzovik-deep-cache.json и тот же выходной формат
  (data/WebReviews/reviews-otzovik.{csv,json}).

Запуск:
    python scripts/parse-otzovik-interactive.py
"""

import sys
import time
import importlib.util
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# чтобы print Unicode не падал в Windows-консоли
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
TMP_DIR = PROJECT_ROOT / "tmp"
STORAGE_STATE = TMP_DIR / "otzovik-storage.json"
CAPTCHA_FLAG = TMP_DIR / "otzovik-captcha-pending.txt"

# импортируем функции из основного парсера (имя файла с дефисом — через importlib)
_spec = importlib.util.spec_from_file_location("otz", Path(__file__).parent / "parse-otzovik.py")
otz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(otz)

DEEP_DELAY_SEC = otz.DEEP_DELAY_SEC  # 12 сек — оставляем как есть


def wait_for_captcha_solved(page, url, label=""):
    """Грузит url. Если на нём капча — ставит паузу и ждёт, пока Маришка введёт код.

    Возвращает финальный HTML после прохождения капчи (или сразу, если её не было).
    """
    page.goto(url, timeout=60000)
    # дать странице прорисоваться
    page.wait_for_load_state('domcontentloaded')
    time.sleep(2)

    while True:
        html = page.content()
        title = page.title()
        if not otz.is_captcha(html, title):
            return html
        print(f"\n  [!] Капча на {label or url}", flush=True)
        print("      Реши её в открывшемся окне Chromium и скажи Клоду 'решила'.", flush=True)
        TMP_DIR.mkdir(exist_ok=True)
        CAPTCHA_FLAG.write_text(f"captcha pending at {url}", encoding='utf-8')
        # ждём, пока Клод удалит файл-флаг (по сигналу Маришки)
        while CAPTCHA_FLAG.exists():
            time.sleep(2)
        print("      [ok] флаг снят, продолжаю", flush=True)
        # после ввода капчи Отзовик редиректит обратно — но на всякий случай перезагрузим
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)
        except Exception as e:
            print(f"      ошибка перезагрузки: {e}")
            time.sleep(3)


def scrape_card_interactive(page, slug, title, start_url):
    """Аналог otz.scrape_card, но с интерактивным проходом капчи."""
    all_reviews = []
    print(f"\n  [{slug}] {title}")
    print(f"  URL: {start_url}")

    html = wait_for_captcha_solved(page, start_url, label=f"{slug} стр.1")

    TMP_DIR.mkdir(exist_ok=True)
    with open(TMP_DIR / f"otzovik-{slug}.html", 'w', encoding='utf-8') as f:
        f.write(html)

    soup = BeautifulSoup(html, 'html.parser')
    total_pages = otz.get_total_pages(soup)
    print(f"  Страниц: {total_pages}")

    reviews = otz.parse_reviews_from_html(html, start_url, title)
    all_reviews.extend(reviews)
    print(f"  Стр. 1: {len(reviews)} отзывов")

    for page_num in range(2, total_pages + 1):
        time.sleep(4)
        page_url = f"{start_url}{page_num}/"
        try:
            html = wait_for_captcha_solved(page, page_url, label=f"{slug} стр.{page_num}")
            reviews = otz.parse_reviews_from_html(html, page_url, title)
            all_reviews.extend(reviews)
            print(f"  Стр. {page_num}: {len(reviews)} отзывов")
        except Exception as e:
            print(f"  Стр. {page_num}: ошибка — {e}")

    return all_reviews


def fetch_review_page_interactive(page, url):
    """Тянет страницу отдельного отзыва с интерактивным проходом капчи.

    Возвращает (data, status), где status: 'ok' | 'fail'.
    'captcha' тут не возвращаем — мы просто ждём Маришку.
    """
    try:
        html = wait_for_captcha_solved(page, url, label=url)
        time.sleep(DEEP_DELAY_SEC)
    except Exception as e:
        print(f"    fail {url}: {e}")
        return None, 'fail'

    data = otz.parse_review_page(html)
    if not data.get('text') and not data.get('pros') and not data.get('cons'):
        # пустая страница — возможно, ещё капча проскочила
        return None, 'fail'
    return data, 'ok'


def enrich_with_deep_interactive(reviews, page, context):
    """Аналог otz.enrich_with_deep, но при капче ждёт Маришку, а не отступает."""
    cache = otz.load_deep_cache()
    print(f"\nDeep-enrich: всего {len(reviews)} отзывов, в кэше {len(cache)}")
    print(f"  пауза: {DEEP_DELAY_SEC}s/req (капчу проходишь руками в окне)")

    processed = 0
    save_every = 25
    storage_every = 50

    for i, r in enumerate(reviews):
        url = r.get('url') or ''
        if not url.startswith('http'):
            continue
        if url in cache:
            data = cache[url]
        else:
            data, status = fetch_review_page_interactive(page, url)
            if status == 'ok':
                cache[url] = data
                processed += 1
                if processed % 5 == 0:
                    print(f"  ok: {processed} новых, всего в кэше {len(cache)}, "
                          f"осталось {len(reviews) - i - 1}")
                if processed % save_every == 0:
                    otz.save_deep_cache(cache)
                if processed % storage_every == 0:
                    try:
                        context.storage_state(path=str(STORAGE_STATE))
                    except Exception as e:
                        print(f"    storage_state save failed: {e}")
            else:
                print(f"  fail {url}")
                continue

        if data:
            if data.get('text'):  r['text'] = data['text']
            if data.get('pros'):  r['pros'] = data['pros']
            if data.get('cons'):  r['cons'] = data['cons']
            if data.get('reply'): r['reply'] = data['reply']

    otz.save_deep_cache(cache)
    try:
        context.storage_state(path=str(STORAGE_STATE))
    except Exception as e:
        print(f"  storage_state save failed: {e}")
    print(f"Deep-enrich завершён. Новых обработано: {processed}, в кэше: {len(cache)}")


def main():
    pages = otz.load_pages_registry()
    print(f"Карточек в реестре: {len(pages)}")
    print("=" * 50)

    storage_arg = {}
    if STORAGE_STATE.exists():
        print(f"Подхватываю cookies из {STORAGE_STATE.name}")
        storage_arg = {'storage_state': str(STORAGE_STATE)}

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

        # Этап 1: листинг по 31 карточке
        all_reviews = []
        for i, p_row in enumerate(pages, 1):
            print(f"\n[{i}/{len(pages)}]")
            try:
                reviews = scrape_card_interactive(page, p_row['slug'], p_row['title'], p_row['url'])
                all_reviews.extend(reviews)
                print(f"  Итого с карточки: {len(reviews)}")
            except Exception as e:
                print(f"  ОШИБКА на карточке {p_row['slug']}: {e}")
            # сохраняем cookies после каждой карточки
            try:
                context.storage_state(path=str(STORAGE_STATE))
            except Exception:
                pass
            time.sleep(6)

        # Этап 2: deep-fetch каждой страницы отзыва
        print("\n" + "=" * 50)
        print("Этап 2: deep-fetch отдельных страниц отзывов")
        print("=" * 50)
        combined = otz.deduplicate(all_reviews)
        combined.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00', reverse=True)
        enrich_with_deep_interactive(combined, page, context)

        browser.close()

    print("\nОбъединяю и дедуплицирую...")
    combined.sort(key=lambda x: x['date'] if x['date'] else '0000-00-00', reverse=True)

    otz.save_all(combined)

    print(f"\nВсего уникальных отзывов: {len(combined)}")
    print("\nПервые 3:")
    for r in combined[:3]:
        print(f"  [{r['date']}] {r['name']} — {r['rating']}★ — {r['source_page'][:50]}")


if __name__ == '__main__':
    main()
