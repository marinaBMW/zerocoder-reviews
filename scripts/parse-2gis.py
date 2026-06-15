"""Парсер отзывов 2ГИС для Zerocoder.

Источник: https://2gis.ru/moscow/firm/70000001057504661/tab/reviews
- SPA, в headless карточки не рендерятся — запускаемся в headed (headless=False).
- Карточки `._1rowqpjv`, 26 шт, без пагинации.
- Текст обрезается «Читать целиком» — кликаем все.
- Данные извлекаем через page.evaluate напрямую (без bs4).

Выход: data/WebReviews/reviews-2gis.{csv,json}
"""
import csv
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "WebReviews"

URL = "https://2gis.ru/moscow/firm/70000001057504661/tab/reviews"
SOURCE_PAGE = "2ГИС: Зерокодер"
FIELDS = ['date', 'name', 'rating', 'title', 'text', 'pros', 'cons', 'reply', 'url', 'source_page']

EXTRACT_JS = r"""() => {
  const cards = document.querySelectorAll('._1rowqpjv');
  const monthsRu = {'январ':1,'феврал':2,'март':3,'апрел':4,'мая':5,'мае':5,'июн':6,'июл':7,'август':8,'сентябр':9,'октябр':10,'ноябр':11,'декабр':12};
  const parseDate = (s) => {
    const m = s.toLowerCase().match(/(\d{1,2})\s+([а-яё]+)\s+(\d{4})/);
    if (!m) return '';
    let mn = null;
    for (const k of Object.keys(monthsRu)) if (m[2].startsWith(k)) { mn = monthsRu[k]; break; }
    if (!mn) return '';
    return `${m[3]}-${String(mn).padStart(2,'0')}-${String(parseInt(m[1])).padStart(2,'0')}`;
  };
  const out = [];
  for (const card of cards) {
    const nameEl = card.querySelector('span[title]');
    const name = nameEl ? nameEl.getAttribute('title') : '';
    const full = card.querySelectorAll('svg[color="#ffb81c"]').length;
    const empty = card.querySelectorAll('svg[color="#929292"]').length;
    let rating = null;
    if (full + empty >= 5 && full <= 5) rating = full;
    const textFull = card.innerText || '';
    const dm = textFull.match(/(\d{1,2}\s+[а-яё]+\s+\d{4})/i);
    const date = dm ? parseDate(dm[0]) : '';
    let text = '';
    if (dm) {
      let rest = textFull.slice(dm.index + dm[0].length).trim();
      for (const marker of ['Читать целиком','Читать полностью','Полезно?']) {
        const i = rest.indexOf(marker);
        if (i > 0) { rest = rest.slice(0, i).trim(); break; }
      }
      text = rest.trim();
    }
    let reply = '';
    const rm = textFull.match(/(?:Ответ владельца|Официальный ответ|Представитель)\s*[\n:]\s*([\s\S]*?)(?=\nПолезно\?|\nЧитать целиком|$)/i);
    if (rm) reply = rm[1].trim();
    out.push({name, rating, date, text, reply});
  }
  return out;
}"""


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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
        # ждём появления карточек
        try:
            page.wait_for_selector('._1rowqpjv', timeout=30000)
        except Exception as e:
            print(f"  карточки не дождались: {e}")
        time.sleep(3)
        # подкрутка + клик «Читать целиком»
        for _ in range(5):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(400)
        page.evaluate("""() => {
            document.querySelectorAll('span, button').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t === 'Читать целиком' || t === 'Читать полностью') {
                    try { el.click(); } catch(_) {}
                }
            });
        }""")
        time.sleep(2)
        data = page.evaluate(EXTRACT_JS)
        browser.close()
    return data


def main():
    print("Парсер 2ГИС -> reviews-2gis.{csv,json}")
    print("=" * 50)
    data = scrape()
    print(f"\nКарточек извлечено: {len(data)}")
    reviews = []
    for d in data:
        if not d.get('name'):
            continue
        reviews.append({
            'date': d.get('date') or '',
            'name': d.get('name') or '',
            'rating': d.get('rating'),
            'title': '',
            'text': d.get('text') or '',
            'pros': '',
            'cons': '',
            'reply': d.get('reply') or '',
            'url': URL,
            'source_page': SOURCE_PAGE,
        })
    reviews.sort(key=lambda r: r.get('date') or '0000-00-00', reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / 'reviews-2gis.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(reviews)
    json_path = OUT_DIR / 'reviews-2gis.json'
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
            print(f"  [{r['date']}] {r['name']} - {r['rating']}* - {(r['text'] or '')[:60]}")


if __name__ == '__main__':
    main()
