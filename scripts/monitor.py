"""
Мониторинг новых отзывов о Zerocoder.
Запускается автоматически через Windows Task Scheduler раз в 14 дней.
Сравнивает текущее количество отзывов с сохранёнными данными и отправляет отчёт на email.
"""

import json
import smtplib
import ssl
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data" / "WebReviews"
CONFIG_PATH = Path(__file__).parent / "monitor-config.json"
BASELINE_PATH = Path(__file__).parent.parent / "data" / "monitor-baseline.json"

# Площадки, которые требуют браузера или ручной проверки
MANUAL_PLATFORMS = [
    ("Отзовик (university-main)", "https://otzovik.com/reviews/zerocoder_ru-perviy_universitet_zerokodinga/"),
    ("Отзовик (intensiv-mobile)", "https://otzovik.com/reviews/zerocoder-intensiv_po_razrabotke_mobilnih_prilozheniy/"),
    ("Отзовик (intensiv-python)", "https://otzovik.com/reviews/zerocoder_ru-intensiv_po_programmirovaniyu_na_python_s_pomoschyu_chatgpt/"),
    ("Отзовик (intensiv-prompt)", "https://otzovik.com/reviews/zerocoder_ru-intensiv_po_promt_inzhiniringu/"),
    ("TutorTop", "https://tutortop.ru/school-reviews/zero-coder/"),
    ("okursah", "https://okursah.ru/s/zerocoder/reviews"),
    ("skill2go", "https://skill2go.com/ru/a/zerocoder/"),
    ("KursHub", "https://kurshub.ru/reviews/zerocoder-ru/"),
    ("2ГИС", "https://2gis.ru/moscow/firm/70000001057504661/tab/reviews"),
    ("iRecommend", "https://irecommend.ru/content/sait-zerokoder-0"),
]

MANUAL_CHECK_PLATFORMS = [
    ("Яндекс Карты", "https://yandex.ru/maps/org/zerokoder/149083959380/reviews/"),
    ("Google Maps", "https://www.google.com/maps/place/ООО+«Зерокодер»/@55.8015997,37.566421,15z"),
]

SCRIPTS = {
    "Отзовик": "parse-otzovik.py",
    "TutorTop": "parse-tutortop.py",
    "okursah": "parse-okursah.py",
    "skill2go": "parse-skill2go.py",
    "KursHub": "parse-kurshub.py",
    "2ГИС": "parse-2gis.py",
    "iRecommend": "parse-irecommend.py",
    "Яндекс Карты": "parse-yandex.py",
}


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_baseline():
    if BASELINE_PATH.exists():
        with open(BASELINE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_baseline(baseline):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)


def get_current_counts():
    """Считаем отзывы из сохранённых JSON-файлов."""
    counts = {}
    for json_file in DATA_DIR.glob("reviews-*.json"):
        name = json_file.stem.replace("reviews-", "")
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            counts[name] = len(data)
        except Exception:
            counts[name] = 0
    return counts


def check_pgdv():
    """Единственная площадка, которую можно проверить без браузера."""
    try:
        r = requests.get(
            "https://pgdv.ru/reviews/zerocoder-otzyvy",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.ec-message")
        return len(items)
    except Exception:
        return None


def build_email(current_counts, baseline, pgdv_live):
    today = date.today().strftime("%d.%m.%Y")

    # Определяем изменения
    changes = []
    for name, count in current_counts.items():
        prev = baseline.get(name, count)
        diff = count - prev
        if diff > 0:
            changes.append((name, prev, count, diff))

    # pgdv live check
    pgdv_note = ""
    if pgdv_live is not None:
        pgdv_prev = baseline.get("pgdv", current_counts.get("pgdv", 0))
        pgdv_diff = pgdv_live - pgdv_prev
        if pgdv_diff > 0:
            pgdv_note = f"⚡ pgdv.ru: было {pgdv_prev}, стало {pgdv_live} (+{pgdv_diff} новых)"
        else:
            pgdv_note = f"pgdv.ru: {pgdv_live} отзывов, новых нет"
    else:
        pgdv_note = "pgdv.ru: не удалось проверить автоматически"

    subject = f"Zerocoder — мониторинг отзывов {today}"

    lines = [
        f"Привет, Маришка! Отчёт по отзывам за {today}.",
        "",
        "── АВТОМАТИЧЕСКИ ПРОВЕРЕНО ──────────────────────",
        pgdv_note,
        "",
    ]

    if changes:
        lines.append("🔔 ОБНАРУЖЕНЫ НОВЫЕ ОТЗЫВЫ в сохранённых файлах:")
        for name, prev, curr, diff in changes:
            lines.append(f"  • {name}: было {prev}, стало {curr} (+{diff})")
        lines.append("")
    else:
        lines.append("В сохранённых файлах изменений нет.")
        lines.append("")

    lines += [
        "── ЗАПУСТИ СКРИПТЫ (нужен браузер + твой Enter) ─",
        "Открой PowerShell в папке zerocoder-reviews и запусти:",
        "",
    ]
    for name, url in MANUAL_PLATFORMS:
        script = SCRIPTS.get(name.split(" ")[0], "")
        if script:
            lines.append(f"  python scripts/{script}")
        lines.append(f"  {url}")
        lines.append("")

    lines += [
        "── ПРОВЕРЬ ВРУЧНУЮ (скрипт не достаёт) ─────────",
    ]
    for name, url in MANUAL_CHECK_PLATFORMS:
        lines.append(f"  {name}: {url}")

    lines += [
        "",
        "─────────────────────────────────────────────────",
        f"Текущие счётчики по файлам:",
    ]
    for name, count in sorted(current_counts.items()):
        prev = baseline.get(name, count)
        diff = count - prev
        mark = f" (+{diff})" if diff > 0 else ""
        lines.append(f"  {name}: {count}{mark}")

    return subject, "\n".join(lines)


def send_email(subject, body, config):
    msg = MIMEMultipart()
    msg["From"] = config["email_from"]
    msg["To"] = config["email_to"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(config["email_from"], config["gmail_app_password"])
        server.sendmail(config["email_from"], config["email_to"], msg.as_bytes())


def main():
    print(f"Мониторинг отзывов — {date.today()}")
    print("=" * 50)

    config = load_config()
    baseline = load_baseline()

    print("Считаю текущие отзывы из файлов...")
    current_counts = get_current_counts()
    for name, count in sorted(current_counts.items()):
        print(f"  {name}: {count}")

    print("Проверяю pgdv.ru без браузера...")
    pgdv_live = check_pgdv()
    print(f"  pgdv live: {pgdv_live}")

    subject, body = build_email(current_counts, baseline, pgdv_live)

    print("Отправляю письмо...")
    try:
        send_email(subject, body, config)
        print(f"  Отправлено на {config['email_to']}")
    except Exception as e:
        print(f"  Ошибка отправки: {e}")
        print("  Тело письма:")
        print(body)

    # Обновляем baseline
    save_baseline(current_counts)
    print("Baseline обновлён.")


if __name__ == "__main__":
    main()
