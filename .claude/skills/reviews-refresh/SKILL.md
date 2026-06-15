---
name: reviews-refresh
description: Полное обновление дашборда отзывов Zerocoder — оркестрирует цепочку подагентов (review-normalizer → review-analyst → insights-extractor → dashboard-builder). Используй, когда обновились данные в data/GC-Reviews/ или data/WebReviews/ и нужно пересобрать reports/{date}-reviews-dashboard.html и CSV для Google Sheets.
---

# Скилл: полное обновление дашборда отзывов

Маришка вызывает этот скилл (`/reviews-refresh`), когда хочет пересобрать дашборд по последним данным.

## Что делать пошагово

Подагенты должны быть вызваны строго в этом порядке — каждый зависит от вывода предыдущего.

### 1. `review-normalizer`

Вызови подагента `review-normalizer`. Он запустит `python scripts/normalize-reviews.py` и пересоберёт `data/unified-reviews.csv` из всех GC-Reviews и WebReviews. Дождись завершения и проверь итоговое количество строк по источникам.

### 2. `review-analyst`

Вызови `review-analyst`. Он запустит `python scripts/analyze-reviews.py` и обновит `tmp/dashboard-data.json` (агрегаты по площадкам, курсам, темам, динамике). Блок `insights` оставит пустым.

### 3. `insights-extractor`

Вызови `insights-extractor`. Он прочитает `data/unified-reviews.csv`, отберёт выборку и сформирует инсайты для отдела продаж и маркетинга. Запишет:
- `reports/{YYYY-MM-DD}-sales-insights.md`
- Обновит блок `insights` в `tmp/dashboard-data.json`

**Важно:** перед записью подагент проверит, что каждая цитата находится в исходном CSV (grep'ом). Если что-то не найдено — выкинет и подберёт другую. Никаких выдуманных цитат.

### 4. `dashboard-builder`

Вызови `dashboard-builder`. Он запустит `python scripts/build-reviews-dashboard.py`:
- `reports/{YYYY-MM-DD}-reviews-dashboard.html` — главный HTML-дашборд (тёмная тема, как `2026-05-15-analytics-dashboard.html`).
- `reports/sheets/*.csv` — плоские CSV под импорт в Google Sheets.

## Финальный отчёт Маришке

После завершения цепочки коротко скажи:
- Путь к новому HTML-дашборду
- Сколько отзывов всего, сколько с ответом (% по площадкам)
- Топ-2 самых ярких изменения относительно предыдущего снимка (если ты можешь сравнить — например, новый «антитоп-курс» или резко выросшая тема)
- Что не сделалось (если есть ошибки в любом из шагов)

## Что НЕ делать

- Не пропускай шаги — порядок строгий.
- Не запускай парсеры внешних площадок (это отдельный скилл `reviews-parse-otzovik`).
- Не предлагай ответы на отзывы (это `reviews-unanswered`).
- Не модифицируй существующие данные в `data/GC-Reviews/` и `data/WebReviews/` — это входные данные.
