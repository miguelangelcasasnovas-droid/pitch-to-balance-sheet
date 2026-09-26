"""Medición de la capa de texto de un PDF con pdfplumber (decisión 3 y sección 7.1 del plan).

El criterio se fijó en docs/estado.md antes de medir:
- caracteres de una página: los no blancos de page.extract_text();
- página con texto: 200 caracteres o más;
- PDF de texto con el 80% o más de páginas con texto, de imagen con menos del 20%,
  y mixto entre medias.
Añadido por decisión del usuario del 26/09/2026: si pdfplumber no puede abrir el PDF, se abre con
pypdfium2 y los caracteres son los no blancos de su texto (get_text_range()).
"""

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pypdfium2

MIN_CHARS_TEXT_PAGE = 200
KEYWORDS = {
    "ingresos": ("turnover", "revenue"),
    "personal": ("staff costs", "wages"),
}


@dataclass(frozen=True)
class TextLayer:
    chars_per_page: tuple[int, ...]
    keyword_pages: dict[str, tuple[int, ...]]  # término -> páginas (desde 1) donde aparece
    engine: str = "pdfplumber"

    @property
    def pages(self) -> int:
        return len(self.chars_per_page)

    @property
    def text_pages(self) -> int:
        return sum(chars >= MIN_CHARS_TEXT_PAGE for chars in self.chars_per_page)

    @property
    def classification(self) -> str:
        return classify(self.chars_per_page)

    def keywords_found(self, group: str) -> tuple[str, ...]:
        return tuple(term for term in KEYWORDS[group] if self.keyword_pages.get(term))


def classify(chars_per_page: tuple[int, ...] | list[int]) -> str:
    """texto (>= 80% de páginas con texto), imagen (< 20%) o mixto."""
    if not chars_per_page:
        raise ValueError("El PDF no tiene páginas")
    total = len(chars_per_page)
    with_text = sum(chars >= MIN_CHARS_TEXT_PAGE for chars in chars_per_page)
    # En enteros, para que los límites del 20% y el 80% sean exactos.
    if with_text * 5 >= total * 4:
        return "texto"
    if with_text * 5 < total:
        return "imagen"
    return "mixto"


def _page_texts_pdfplumber(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _page_texts_pypdfium2(path: Path) -> list[str]:
    pdf = pypdfium2.PdfDocument(path)
    try:
        return [pdf[index].get_textpage().get_text_range() for index in range(len(pdf))]
    finally:
        pdf.close()


def measure(path: Path) -> TextLayer:
    """Mide con pdfplumber. Si no puede abrir el PDF, con pypdfium2; si tampoco, error."""
    try:
        texts, engine = _page_texts_pdfplumber(path), "pdfplumber"
    except Exception:
        texts, engine = _page_texts_pypdfium2(path), "pypdfium2"
    chars_per_page = []
    keyword_pages: dict[str, list[int]] = {
        term: [] for terms in KEYWORDS.values() for term in terms
    }
    for number, text in enumerate(texts, start=1):
        chars_per_page.append(sum(not char.isspace() for char in text))
        normalized = " ".join(text.lower().split())
        for term, pages in keyword_pages.items():
            if term in normalized:
                pages.append(number)
    return TextLayer(
        chars_per_page=tuple(chars_per_page),
        keyword_pages={term: tuple(pages) for term, pages in keyword_pages.items()},
        engine=engine,
    )
