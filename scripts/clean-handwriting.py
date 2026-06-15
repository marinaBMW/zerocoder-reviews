"""
Удаление рукописного текста со сканированного PDF — версия с Tesseract OCR.

Идея: Tesseract распознаёт печатный текст и возвращает bounding box каждого слова
с confidence. Всё, что попало в эти боксы (с conf > порога) — оставляем.
Длинные линии формы (рамки таблиц, подчёркивания) защищаем отдельно через морфологию.
Всё остальное — рукопись, кружочки, росчерки — стираем.
"""

import sys
from pathlib import Path
import fitz
import numpy as np
import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

SRC = Path(r"C:\Users\bogac\Education\zerocoder-reviews\tmp\report.pdf")
OUT_DIR = Path(r"C:\Users\bogac\Education\zerocoder-reviews\tmp\cleaned")
OUT_PDF = Path(r"C:\Users\bogac\Education\zerocoder-reviews\tmp\report-blank.pdf")
DPI = 300

OCR_CONF = 30                # минимальная уверенность OCR
BOX_PADDING = 3              # расширяем bbox вокруг слова
LINE_MIN_FRAC = 60           # минимальная длина линии формы = ширина/высота страницы / N
HW_STROKE_HW_THRESH = 2.4    # медианная полутолщина >= этого — рукопись
MAX_PRINT_HEIGHT = 45        # высота слова > этого — не печать (заголовки исключение)
TESS_CONFIG = "--psm 6"      # uniform block of text — лучше для форм


def render_page(page, dpi=DPI):
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return img


def extract_lines(binary):
    h, w = binary.shape
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, w // LINE_MIN_FRAC), 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=1)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, h // LINE_MIN_FRAC)))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=1)
    lines = cv2.bitwise_or(h_lines, v_lines)
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8), iterations=1)
    return lines


def ocr_boxes(gray, binary, stroke_dist):
    """Объединяет результаты двух OCR-проходов (PSM 6 и 11) и фильтрует ложные позитивы
    по толщине штриха внутри bbox."""
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    seen_boxes = []

    # Один проход PSM 6 — uniform block of text
    try:
        data = pytesseract.image_to_data(
            gray, output_type=pytesseract.Output.DICT, lang="eng", config=TESS_CONFIG
        )
    except Exception:
        return mask

    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text or len(text) < 1:
            continue
        try:
            conf = float(data["conf"][i])
        except ValueError:
            continue
        if conf < OCR_CONF:
            continue
        x = max(0, data["left"][i] - BOX_PADDING)
        y = max(0, data["top"][i] - BOX_PADDING)
        bw = data["width"][i] + 2 * BOX_PADDING
        bh = data["height"][i] + 2 * BOX_PADDING
        x2, y2 = min(w, x + bw), min(h, y + bh)
        if x2 <= x or y2 <= y:
            continue

        # Слово слишком высокое — точно не строка обычной печати
        if (y2 - y) > MAX_PRINT_HEIGHT:
            continue

        # Толщина штриха внутри бокса
        roi_bin = binary[y:y2, x:x2]
        roi_dist = stroke_dist[y:y2, x:x2]
        ink = roi_dist[roi_bin > 0]
        if ink.size < 20:
            continue
        median_hw = float(np.median(ink))
        if median_hw >= HW_STROKE_HW_THRESH:
            continue  # рукопись, не печать

        cv2.rectangle(mask, (x, y), (x2, y2), 255, -1)
        seen_boxes.append((x, y, x2, y2))
    return mask


def clean_page(gray):
    # Бинарная маска чернил
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 12
    )
    # Distance transform для оценки толщины штриха в любом регионе
    stroke_dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    # Линии формы (защищаем)
    lines = extract_lines(binary)
    # OCR-зона печатного текста (защищаем), с проверкой толщины штриха
    text_zone = ocr_boxes(gray, binary, stroke_dist)
    # Объединяем защищённые зоны
    protect = cv2.bitwise_or(text_zone, lines)
    # Берём только чернила внутри защищённых зон
    keep_ink = cv2.bitwise_and(binary, protect)
    # Инвертируем: чёрные надписи на белом
    out = 255 - keep_ink
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    only_first = "--first" in sys.argv

    doc = fitz.open(SRC)
    pages_idx = [0] if only_first else range(doc.page_count)
    cleaned = []
    for i in pages_idx:
        page = doc.load_page(i)
        gray = render_page(page)
        out = clean_page(gray)
        cv2.imwrite(str(OUT_DIR / f"page-{i+1}-cleaned.png"), out)
        cleaned.append(out)
        print(f"page {i+1}: ok")

    target = OUT_PDF.with_name("report-blank-first.pdf") if only_first else OUT_PDF
    out_doc = fitz.open()
    for img in cleaned:
        h, w = img.shape
        rect = fitz.Rect(0, 0, w, h)
        new_page = out_doc.new_page(width=w, height=h)
        ok, buf = cv2.imencode(".png", img)
        new_page.insert_image(rect, stream=buf.tobytes())
    out_doc.save(target)
    out_doc.close()
    doc.close()
    print(f"saved: {target}")


if __name__ == "__main__":
    main()
