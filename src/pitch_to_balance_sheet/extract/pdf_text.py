"""Palabras de una página con capa de texto, con su posición, sin OCR.

pdfplumber da cada palabra con su caja en puntos; aquí se pasan a píxeles de la página
renderizada a 300 ppp, para leer las tablas igual que el OCR y recortar las filas de la imagen.
La imagen se guarda en data/interim/text/<sha256 del PDF>/page-NNN.png.
"""

from pathlib import Path

import pdfplumber

from pitch_to_balance_sheet.extract.ocr import OCR_DPI, render_page
from pitch_to_balance_sheet.extract.tables import Observation


def page_observations(pdf_path: Path, page: int, dpi: int = OCR_DPI) -> list[Observation]:
    scale = dpi / 72
    with pdfplumber.open(pdf_path) as pdf:
        words = pdf.pages[page - 1].extract_words()
    return [Observation(w["text"], 1.0,
                        (w["x0"] * scale, w["top"] * scale, w["x1"] * scale, w["bottom"] * scale))
            for w in words]


def page_image(pdf_path: Path, sha256: str, page: int, out_dir: Path) -> Path:
    path = out_dir / sha256 / f"page-{page:03d}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        render_page(pdf_path, page).save(path)
    return path
