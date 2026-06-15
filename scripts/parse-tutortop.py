"""Парсер отзывов TutorTop для Zerocoder.

Источник: https://tutortop.ru/school-reviews/zero-coder/
- 4 страницы пагинации (page/2 .. page/N), всего ~123 отзыва.
- HTML отдаётся сразу без JS, парсим через requests + BeautifulSoup.
- На карточке — микроразметка Schema.org/Review.

Выход:
    data/WebReviews/reviews-tutortop.csv  (UTF-8 BOM, для Excel)
    data/WebReviews/reviews-tutortop.json
Схема: date, name, rating, title, text, pros, cons, reply, url, source_page
"""
import csv
import json
import re
import sys
import time
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

BASE = "https://tutortop.ru/school-reviews/zero-coder/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']
SOURCE_PAGE = 'TutorTop: ZeroCoder'

DELAY_SEC = 2  # между страницами пагинации


def page_url(n):
    return BASE if n == 1 else f"{BASE}page/{n}/"


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def parse_data_date(s):
    """20231112 -> 2023-11-12"""
    if not s or len(s) != 8 or not s.isdigit():
        return ''
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def parse_rating(s):
    """'5,0' / '4,0' -> 5 / 4 (int если целое, иначе float)"""
    if not s:
        return None
    s = s.replace(',', '.').strip()
    try:
        v = float(s)
        if v == int(v):
            return int(v)
        return v
    except ValueError:
        return None


def extract_section(text, marker, next_markers):
    """Достаёт фрагмент текста между marker и любым из next_markers (или до конца)."""
    if not text:
        return ''
    pattern = re.compile(rf'{marker}\s*[:\-]?\s*(.*?)(?={"|".join(next_markers)}|$)', re.I | re.S)
    m = pattern.search(text)
    return m.group(1).strip() if m else ''


def parse_card(card):
    """Распарсить одну карточку отзыва. Возвращает dict схемы FIELDS."""
    rid = card.get('id') or ''
    date = parse_data_date(card.get('data-date'))

    author_el = card.select_one('[itemprop="author"]')
    name = author_el.get_text(strip=True) if author_el else ''

    rating_el = card.select_one('[itemprop="ratingValue"]')
    rating = parse_rating(rating_el.get_text(strip=True) if rating_el else '')

    title_el = card.select_one('h2[itemprop="name"]')
    title = title_el.get_text(strip=True) if title_el else ''

    # Текст отзыва.
    desc_el = card.select_one('[itemprop="description"]')
    if desc_el:
        text = desc_el.get_text(separator='\n').strip()
    else:
        # На свежих карточках description отсутствует — текст вёрстается обычными <p>.
        # Берём всю текстовую массу карточки, дальше выделим pros/cons и подчистим хвосты.
        text = card.get_text(separator='\n')

    # Если title из h2 пустой (свежие карточки) — он лежит в тексте после звёзд оценки
    # и до секции "Достоинства". Пример: "...★ ★ ★ ★ ★\nПервый практический курс...\nДостоинства\n..."
    if not title and text:
        # удалим повторяющиеся пустые строки
        lines = [ln.strip() for ln in text.split('\n')]
        lines = [ln for ln in lines if ln and ln != '★']
        # ищем последнюю строку с рейтингом (содержит запятую и цифру) либо чистую цифру,
        # после неё идёт title до "Достоинства"
        # проще: найти индекс первого "Достоинства" и взять предыдущую непустую короткую строку как заголовок
        for i, ln in enumerate(lines):
            if 'Достоинства' in ln:
                # ищем заголовок выше — последняя «осмысленная» короткая строка
                for j in range(i - 1, -1, -1):
                    cand = lines[j]
                    # пропускаем чисто-цифровые/рейтинговые
                    if re.fullmatch(r'\d+([.,]\d+)?', cand):
                        continue
                    if re.fullmatch(r'\d+\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\w*\s+\d{4}.*', cand, re.I):
                        continue
                    if cand == name:
                        break
                    if 3 < len(cand) < 200:
                        title = cand
                        break
                break

    # Pros / Cons. Список маркеров, которые завершают секцию.
    section_end = (
        r'Недостатки|Достоинства|Другие впечатления|Поддержка Университета|Похожие курсы|Ответить|Читать полностью'
    )
    pros, cons = '', ''
    if text:
        m_pros = re.search(rf'Достоинства\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:{section_end})|\Z)',
                           text, re.S | re.I)
        if m_pros:
            pros = m_pros.group(1).strip()
        m_cons = re.search(rf'Недостатки\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:{section_end})|\Z)',
                           text, re.S | re.I)
        if m_cons:
            cons = m_cons.group(1).strip()

    # Reply: текст после H5 "Поддержка Университета Zerocoder"
    reply = ''
    reply_header = None
    for h5 in card.select('h5'):
        if 'Поддержка Университета' in h5.get_text():
            reply_header = h5
            break
    if reply_header:
        # Поднимаемся к контейнеру комментария и берём следующий блок с длинным текстом
        wrap = reply_header.parent
        depth = 0
        while wrap and wrap is not card and depth < 6:
            for cand in wrap.find_all(['p', 'div']):
                t = cand.get_text(separator='\n').strip()
                # пропускаем шапку и короткие технические надписи
                if (len(t) > 40
                        and 'Поддержка Университета' not in t
                        and 'Школа' != t.strip()
                        and not t.startswith('Поддержка')):
                    reply = t
                    break
            if reply:
                break
            wrap = wrap.parent
            depth += 1

    # Чистим текст от хвостов
    if text:
        # отрезаем всё после маркеров не относящихся к отзыву
        for marker in ['Похожие курсы', 'Поддержка Университета', 'Ответить\n', 'Читать полностью']:
            i = text.find(marker)
            if i > 100:  # маркер реально дальше начала
                text = text[:i].rstrip()
        # для карточек без itemprop=description — отрежем шапку (имя + дата + рейтинг + заголовок)
        if not desc_el:
            # шапка обычно заканчивается заголовком (title)
            if title and title in text:
                idx = text.find(title) + len(title)
                text = text[idx:].lstrip('\n ').strip()

    # url с якорем на карточку
    url = f"{BASE}#{rid}" if rid else BASE

    return {
        'date': date,
        'name': name,
        'rating': rating,
        'title': title,
        'text': text,
        'pros': pros,
        'cons': cons,
        'reply': reply,
        'url': url,
        'source_page': SOURCE_PAGE,
    }


def scrape_all():
    all_reviews = []
    n = 1
    while True:
        url = page_url(n)
        print(f"  Стр. {n}: {url}")
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  ошибка загрузки: {e}")
            break
        TMP_DIR.mkdir(exist_ok=True)
        if n == 1:
            (TMP_DIR / "tutortop-page1.html").write_text(html, encoding='utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('[itemprop="review"][id^="review"][data-date]')
        print(f"    карточек: {len(cards)}")
        if not cards:
            break
        for c in cards:
            all_reviews.append(parse_card(c))
        # есть ли следующая страница в пагинации?
        next_link = soup.select_one(f'a[href*="/page/{n+1}/"]')
        if not next_link and len(cards) < 40:
            # неполная страница и нет ссылки на следующую — конец
            break
        n += 1
        time.sleep(DELAY_SEC)
    return all_reviews


def deduplicate(reviews):
    seen = set()
    out = []
    for r in reviews:
        # id в url содержит уникальный reviewID
        key = r.get('url')
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def save_all(reviews):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-tutortop.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(reviews)
    json_path = OUT_DIR / 'reviews-tutortop.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print(f"\nЗаписано: {len(reviews)} отзывов")
    print(f"  -> {csv_path.name}")
    print(f"  -> {json_path.name}")


def main():
    print("Парсер TutorTop -> data/WebReviews/reviews-tutortop.{csv,json}")
    print("=" * 50)
    reviews = scrape_all()
    print(f"\nСырых отзывов: {len(reviews)}")
    reviews = deduplicate(reviews)
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    save_all(reviews)
    # краткая статистика
    rated = [r for r in reviews if r.get('rating') is not None]
    avg = sum(r['rating'] for r in rated) / len(rated) if rated else 0
    with_text = sum(1 for r in reviews if r.get('text'))
    with_reply = sum(1 for r in reviews if r.get('reply'))
    print(f"\nСтатистика:")
    print(f"  С текстом: {with_text}/{len(reviews)}")
    print(f"  С ответом школы: {with_reply}/{len(reviews)}")
    print(f"  Средний рейтинг: {avg:.2f}")
    if reviews:
        print(f"\nПервые 3:")
        for r in reviews[:3]:
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {r['title'][:60]}")


if __name__ == '__main__':
    main()
