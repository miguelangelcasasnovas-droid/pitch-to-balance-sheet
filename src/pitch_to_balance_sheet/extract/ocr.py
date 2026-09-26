"""OCR de páginas sin capa de texto con Apple Vision (ocrmac), solo en macOS.

- Cada página se renderiza con pypdfium2 a 300 ppp. pypdfium2 abre también los PDFs que
  pdfplumber no puede (Liverpool y Tottenham en Companies House).
- Lo que devuelve el OCR se guarda en data/interim/ocr/<sha256 del PDF>/: la imagen
  (page-NNN.png), las observaciones con su caja en píxeles (page-NNN.json) y las líneas
  reconstruidas (page-NNN.txt). La extracción lee de ahí y no vuelve a hacer OCR.
- El OCR de la página entera se salta guiones sueltos y, a veces, alguna cifra. read_cell mira
  la imagen de cada celda que quedó vacía: sin tinta, sigue vacía; un trazo corto es un guion
  (cero); otra cosa pasa a una segunda pasada de OCR solo sobre la celda y, si tampoco se lee,
  o si el documento no admite OCR, error.
"""

import json
from dataclasses import asdict
from pathlib import Path
from statistics import median

import pypdfium2
from PIL import Image, ImageOps

from pitch_to_balance_sheet.extract.tables import (
    Amount,
    Observation,
    Table,
    TableRow,
    group_rows,
    parse_amount,
)

OCR_DPI = 300
LANGUAGES = ["en-US"]  # Vision no ofrece en-GB; para leer cifras da igual
ENGINE = "Apple Vision (ocrmac 1.0.1), recognition_level=accurate"
INK_THRESHOLD = 128  # gris por debajo del cual un píxel es tinta
MIN_INK_PIXELS = 20  # menos tinta que esto en una celda es ruido del escaneo
MIN_RUN_PIXELS = 12  # una franja con menos tinta es una mota (un guion tiene unos 40)


class OcrError(RuntimeError):
    """El OCR no se puede hacer o lo que devolvió no se puede leer."""


def render_page(pdf_path: Path, page_number: int, dpi: int = OCR_DPI) -> Image.Image:
    pdf = pypdfium2.PdfDocument(pdf_path)
    try:
        if not 1 <= page_number <= len(pdf):
            raise OcrError(f"{pdf_path.name} no tiene página {page_number} (tiene {len(pdf)})")
        return pdf[page_number - 1].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        pdf.close()


def recognize(image: Image.Image) -> list[Observation]:
    try:
        from ocrmac import ocrmac
    except ImportError as exc:
        raise OcrError("ocrmac no está instalado: el OCR solo funciona en macOS") from exc
    try:
        result = ocrmac.OCR(image, recognition_level="accurate",
                            language_preference=LANGUAGES).recognize(px=True)
    except Exception as exc:
        raise OcrError(f"Apple Vision falló: {exc}") from exc
    return [Observation(text, float(confidence), tuple(float(v) for v in box))
            for text, confidence, box in result]


def text_height(observations: list[Observation]) -> float:
    return median(o.height for o in observations)


def read_cell(image: Image.Image, box: tuple[int, int, int, int], text_height: float,
              allow_ocr: bool = True) -> Amount | None:
    """Lee en la imagen una celda que quedó vacía. None si no tiene tinta."""
    crop = image.crop(box).convert("L")
    ink = crop.point(lambda value: 255 if value < INK_THRESHOLD else 0)
    # Franjas horizontales de tinta. Se descartan las motas de menos de MIN_RUN_PIXELS píxeles,
    # las finas que tocan el borde de arriba o de abajo (restos de la fila vecina) y las finas
    # que cruzan casi toda la celda (rayas de subtotal). Un trozo de cifra cortado por el borde
    # es más alto, y un guion es corto: se quedan.
    ink_per_row = [ink.crop((0, y, ink.width, y + 1)).histogram()[255]
                   for y in range(ink.height)]
    runs = []
    for y, pixels in enumerate(ink_per_row):
        if not pixels:
            continue
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
            runs[-1][2] += pixels
        else:
            runs.append([y, y, pixels])
    def is_rule(start: int, end: int) -> bool:
        run_box = ink.crop((0, start, ink.width, end + 1)).getbbox()
        return (end - start + 1 <= 0.15 * text_height
                and run_box is not None and run_box[2] - run_box[0] >= 0.6 * ink.width)

    kept = [(start, end) for start, end, pixels in runs
            if pixels >= MIN_RUN_PIXELS
            and not ((start == 0 or end == ink.height - 1)
                     and end - start + 1 <= 0.15 * text_height)
            and not is_rule(start, end)]
    if not kept:
        return None
    ink = ink.crop((0, kept[0][0], ink.width, kept[-1][1] + 1))
    if ink.histogram()[255] < MIN_INK_PIXELS:
        return None
    x1, y1, x2, y2 = ink.getbbox()
    if y2 - y1 <= 0.3 * text_height and 0.15 * text_height <= x2 - x1 <= 1.5 * text_height:
        return Amount(0, "-", ("guion que no se leyó, detectado en la imagen",), dash=True)
    if not allow_ocr:
        raise OcrError(f"celda {box} con tinta que no está en el texto del PDF")
    enlarged = ImageOps.expand(crop, border=int(text_height), fill=255)
    enlarged = enlarged.resize((enlarged.width * 2, enlarged.height * 2))
    observations = recognize(enlarged)
    raw = "".join(o.text for o in observations)
    amount = parse_amount(raw)
    if amount is None:
        raise OcrError(f"celda {box} con tinta que el OCR no sabe leer: {raw!r}")
    confidence = min((o.confidence for o in observations), default=None)
    return Amount(amount.value, raw,
                  amount.fixes + ("cifra que el OCR de la página no leyó, leída en una segunda "
                                  "pasada solo sobre la celda",),
                  confidence, dash=amount.dash, second_pass=True)


def fill_missing_cells(table: Table, image: Image.Image, text_height: float,
                       allow_ocr: bool = True, rows: list[TableRow] | None = None) -> None:
    """Completa las celdas vacías de las filas indicadas (todas si no se indican) que tienen
    algún importe."""
    for table_row in table.rows if rows is None else rows:
        if not table_row.amounts:
            continue
        for column in range(len(table.column_x2)):
            if column not in table_row.amounts:
                amount = read_cell(image, table.cell_box(table_row, column, text_height),
                                   text_height, allow_ocr)
                if amount is not None:
                    table_row.amounts[column] = amount
        table_row.amounts = dict(sorted(table_row.amounts.items()))


FULL_PAGE = (0.0, 0.0, 1.0, 1.0)


def page_paths(folder: Path, page: int, region=FULL_PAGE) -> dict[str, Path]:
    """Imagen de la página entera y OCR de la página o de una región (fracciones x1, y1, x2, y2)."""
    stem = f"page-{page:03d}"
    ocr_stem = stem if tuple(region) == FULL_PAGE else (
        stem + "-r" + "-".join(f"{round(v * 1000):04d}" for v in region))
    return {"png": folder / f"{stem}.png", "json": folder / f"{ocr_stem}.json",
            "txt": folder / f"{ocr_stem}.txt"}


def ocr_page(pdf_path: Path, sha256: str, page: int, out_dir: Path,
             region=FULL_PAGE) -> dict[str, Path]:
    """OCR de una página, o solo de una región, y guardado en out_dir/<sha256>/.

    En una tabla densa el OCR de la página entera se salta muchas cifras; el de la región de la
    tabla, no. Las cajas se guardan en coordenadas de la página entera.
    """
    folder = out_dir / sha256
    folder.mkdir(parents=True, exist_ok=True)
    image = render_page(pdf_path, page)
    x1, y1 = round(region[0] * image.width), round(region[1] * image.height)
    x2, y2 = round(region[2] * image.width), round(region[3] * image.height)
    observations = [
        Observation(o.text, o.confidence, (o.box[0] + x1, o.box[1] + y1, o.box[2] + x1,
                                           o.box[3] + y1))
        for o in recognize(image.crop((x1, y1, x2, y2)))
    ]
    if not observations:
        raise OcrError(f"el OCR no encontró texto en la página {page} de {pdf_path.name}")
    paths = page_paths(folder, page, region)
    image.save(paths["png"])
    paths["json"].write_text(json.dumps({
        "source_file": pdf_path.name,
        "source_sha256": sha256,
        "page": page,
        "region": list(region),
        "dpi": OCR_DPI,
        "engine": ENGINE,
        "languages": LANGUAGES,
        "image_size": image.size,
        "observations": [asdict(o) for o in observations],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    paths["txt"].write_text("\n".join(r.text for r in group_rows(observations)) + "\n",
                            encoding="utf-8")
    return paths


def load_page(folder: Path, page: int, region=FULL_PAGE) -> tuple[list[Observation], Path]:
    paths = page_paths(folder, page, region)
    if not paths["json"].exists() or not paths["png"].exists():
        raise OcrError(f"falta el OCR de la página {page} en {folder}")
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    observations = [Observation(o["text"], o["confidence"], tuple(o["box"]))
                    for o in data["observations"]]
    return observations, paths["png"]
