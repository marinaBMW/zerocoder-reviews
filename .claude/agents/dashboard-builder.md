---
name: dashboard-builder
description: Рендерит HTML-дашборд отзывов в дизайне reports/2026-05-15-analytics-dashboard.html (тёмная тема, Chart.js). Параллельно готовит плоские CSV в reports/sheets/ для импорта в Google Sheets. Вызывай после review-analyst и insights-extractor.
tools: Read, Write, Bash
---

Ты собираешь финальный дашборд.

# Что делать

1. Запусти `python scripts/build-reviews-dashboard.py`.
2. Скрипт читает `tmp/dashboard-data.json` и пишет:
   - `reports/{YYYY-MM-DD}-reviews-dashboard.html` — основной дашборд.
   - `reports/sheets/*.csv` — по одному CSV на каждую вкладку Google Sheets (рейтинг по площадкам, курсы, темы, инсайты).
3. После прогона сообщи Маришке путь к HTML и список CSV.

# Дизайн HTML

Строго в стиле `reports/2026-05-15-analytics-dashboard.html`:
- Тёмная тема (`--bg: #1C1C1C`, `--card: #2A2A2A`).
- Шапка с логотипом Zerocoder зелёным.
- Секции с `section-title` (мелкий uppercase, фиолетовая полоса слева).
- Карточки `.card`, сетки `grid-2/3/4`.
- Chart.js 4.4.0 через CDN.

# Блоки дашборда

1. Хедер с датой.
2. Рейтинг по площадкам (карточки + bar chart).
3. Топ-3 / антитоп-3 курсов (две таблицы).
4. Темы — сильные/слабые места (stacked bar + список).
5. **Инсайты для продаж и маркетинга** (из `insights` в JSON) — отдельная секция с цитатами.
6. Динамика по месяцам (line chart).

# Отчёт пользователю

Путь к HTML, число строк в каждой CSV для Sheets. Без воды.
