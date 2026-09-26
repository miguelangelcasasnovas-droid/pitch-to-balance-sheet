"""OCR de páginas sin capa de texto con Apple Vision (ocrmac), y lectura de sus tablas.

- Cada página se renderiza con pypdfium2 a 300 ppp. pypdfium2 abre también los PDFs que
  pdfplumber no puede (Liverpool y Tottenham en Companies House).
- El OCR solo funciona en macOS. Lo que devuelve se guarda en data/interim/ocr/<sha256 del PDF>/:
  la imagen (page-NNN.png), las observaciones con su caja en píxeles (page-NNN.json) y las líneas
  reconstruidas (page-NNN.txt). La extracción lee de ahí y no vuelve a hacer OCR.
- Las tablas se leen por posición: cada importe va a la columna de la cabecera "£'000" cuyo borde
  derecho tiene más cerca. parse_amount dice qué ha tenido que corregir de lo que leyó el OCR.
- El OCR de la página entera se salta guiones sueltos y, a veces, alguna cifra. read_cell mira
  la imagen de cada celda que quedó vacía: sin tinta, vacía; un trazo corto, guion (cero); otra
  cosa, segunda pasada de OCR solo sobre la celda, y si tampoco se lee, error.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median

import pypdfium2
from PIL import Image, ImageOps

OCR_DPI = 300
LANGUAGES = ["en-US"]  # Vision no ofrece en-GB; para leer cifras da igual
ENGINE = "Apple Vision (ocrmac 1.0.1), recognition_level=accurate"
# "£'000" y cómo lo lee a veces el OCR: "€'000", "f'000", "E'000". La moneda no se toma de aquí.
UNIT = re.compile(r"^[£€Ef][’'‘`´]?[0O]{3}$")
INK_THRESHOLD = 128  # gris por debajo del cual un píxel es tinta
MIN_INK_PIXELS = 20  # menos tinta que esto en una celda es ruido del escaneo
MIN_RUN_PIXELS = 12  # una franja con menos tinta es una mota (un guion tiene unos 40)
AMOUNT = re.compile(r"^\(?\d{1,3}(,\d{3})*\)?$")
DASHES = {"-", "–", "—", "_"}
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5"})


class OcrError(RuntimeError):
    """El OCR no se puede hacer o lo que devolvió no se puede leer."""


@dataclass(frozen=True)
class Observation:
    text: str
    confidence: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 en píxeles, origen arriba a la izq.

    @property
    def center_y(self) -> float:
        return (self.box[1] + self.box[3]) / 2

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]


@dataclass(frozen=True)
class Token:
    """Una palabra de una observación, con su posición estimada dentro de la caja."""

    text: str
    x1: float
    x2: float
    observation: Observation


@dataclass
class Row:
    observations: list[Observation] = field(default_factory=list)

    @property
    def box(self) -> tuple[float, float, float, float]:
        boxes = [o.box for o in self.observations]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    @property
    def text(self) -> str:
        return " ".join(o.text for o in self.observations)

    def tokens(self) -> list[Token]:
        result = []
        for observation in self.observations:
            x1, _, x2, _ = observation.box
            width = (x2 - x1) / max(len(observation.text), 1)
            for match in re.finditer(r"\S+", observation.text):
                result.append(Token(match.group(), x1 + width * match.start(),
                                    x1 + width * match.end(), observation))
        return result


@dataclass(frozen=True)
class Amount:
    value: int
    raw: str
    fixes: tuple[str, ...] = ()
    confidence: float | None = None


@dataclass
class TableRow:
    label: str  # rótulo normalizado: minúsculas, sin puntuación suelta
    raw_label: str
    note: str | None
    amounts: dict[int, Amount]  # índice de columna -> importe
    row: Row


@dataclass
class Table:
    unit_raw: tuple[str, ...]  # las cabeceras de unidad tal como las leyó el OCR
    column_x2: tuple[float, ...]
    rows: list[TableRow]

    def cell_box(self, table_row: TableRow, column: int, text_height: float):
        """Caja de una celda: junto al borde derecho de su columna, en la banda de su fila.

        Las cifras van alineadas a la derecha, y el paréntesis de cierre sobresale un poco.
        """
        gaps = [b - a for a, b in zip(self.column_x2, self.column_x2[1:], strict=False)]
        width = min(gaps) if gaps else 4 * text_height
        x2 = self.column_x2[column]
        center_y = (table_row.row.box[1] + table_row.row.box[3]) / 2
        return (int(x2 - 0.8 * width), int(center_y - 0.55 * text_height),
                int(x2 + 0.12 * width), int(center_y + 0.55 * text_height))


def parse_amount(raw: str) -> Amount | None:
    """Importe tal como sale del OCR -> entero. None si no parece un importe."""
    text = raw.strip().replace(" ", "")
    if text in DASHES:
        return Amount(0, raw)
    fixes = []
    if re.search(r"\d", text) and re.search(r"[OolIS]", text):
        text = text.translate(DIGIT_LOOKALIKES)
        fixes.append("letra leída en lugar de dígito")
    if re.fullmatch(r"\(?\d{1,3}(\.\d{3})+\)?", text):
        text = text.replace(".", ",")
        fixes.append("punto en lugar de coma de miles")
    if text.startswith("(") != text.endswith(")") and AMOUNT.fullmatch(f"({text.strip('()')})"):
        text = f"({text.strip('()')})"
        fixes.append("paréntesis sin pareja")
    if not AMOUNT.fullmatch(text):
        return None
    value = int(text.strip("()").replace(",", ""))
    return Amount(-value if text.startswith("(") else value, raw, tuple(fixes))


def normalize_label(text: str) -> str:
    text = re.sub(r"[^a-z0-9()/'&,\- ]", " ", text.lower())
    return " ".join(text.split())


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


def group_rows(observations: list[Observation]) -> list[Row]:
    """Agrupa en filas las observaciones cuyo centro vertical está a menos de media altura."""
    if not observations:
        return []
    tolerance = median(o.height for o in observations) / 2
    rows: list[Row] = []
    for observation in sorted(observations, key=lambda o: o.center_y):
        row = rows[-1] if rows else None
        if row and abs(observation.center_y - median(o.center_y for o in row.observations)) \
                <= tolerance:
            row.observations.append(observation)
        else:
            rows.append(Row([observation]))
    for row in rows:
        row.observations.sort(key=lambda o: o.box[0])
    return rows


def read_tables(rows: list[Row]) -> list[Table]:
    """Tablas de la página: cada una empieza en una fila con cabeceras de unidad ("£'000")."""
    tables: list[Table] = []
    for row in rows:
        units = [token for token in row.tokens() if UNIT.fullmatch(token.text)]
        if units:
            tables.append(Table(tuple(t.text for t in units), tuple(t.x2 for t in units), []))
            continue
        if tables:
            tables[-1].rows.append(_table_row(row, tables[-1].column_x2))
    return tables


def _table_row(row: Row, column_x2: tuple[float, ...]) -> TableRow:
    gaps = [b - a for a, b in zip(column_x2, column_x2[1:], strict=False)]
    tolerance = 0.35 * min(gaps) if gaps else 0.1 * column_x2[0]
    label_tokens, amounts = [], {}
    for token in row.tokens():
        amount = parse_amount(token.text)
        distances = [abs(token.x2 - x2) for x2 in column_x2]
        column = distances.index(min(distances))
        if amount is not None and min(distances) <= tolerance:
            if column in amounts:
                raise OcrError(f"dos importes en la misma columna de la fila {row.text!r}")
            amounts[column] = Amount(amount.value, amount.raw, amount.fixes,
                                     token.observation.confidence)
        else:
            label_tokens.append(token.text)
    note = None
    if label_tokens and re.fullmatch(r"\d{1,2}", label_tokens[-1]):
        note = label_tokens.pop()
    raw_label = " ".join(label_tokens)
    return TableRow(normalize_label(raw_label), raw_label, note, dict(sorted(amounts.items())),
                    row)


def read_cell(image: Image.Image, box: tuple[int, int, int, int],
              text_height: float) -> Amount | None:
    """Lee en la imagen una celda que el OCR de la página dejó vacía. None si no tiene tinta."""
    crop = image.crop(box).convert("L")
    ink = crop.point(lambda value: 255 if value < INK_THRESHOLD else 0)
    # Franjas horizontales de tinta. Se descartan las finas que tocan el borde de arriba o de
    # abajo (restos de la fila vecina o de una raya de subtotal) y las motas de menos de
    # MIN_RUN_PIXELS píxeles. Un trozo de cifra cortado por el borde es más alto y se queda.
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
    kept = [(start, end) for start, end, pixels in runs
            if pixels >= MIN_RUN_PIXELS
            and not ((start == 0 or end == ink.height - 1)
                     and end - start + 1 <= 0.15 * text_height)]
    if not kept:
        return None
    ink = ink.crop((0, kept[0][0], ink.width, kept[-1][1] + 1))
    if ink.histogram()[255] < MIN_INK_PIXELS:
        return None
    x1, y1, x2, y2 = ink.getbbox()
    if y2 - y1 <= 0.3 * text_height and 0.15 * text_height <= x2 - x1 <= 1.5 * text_height:
        return Amount(0, "-", ("guion que el OCR no leyó, detectado en la imagen",))
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
                                  "pasada solo sobre la celda",), confidence)


def fill_missing_cells(table: Table, image: Image.Image, text_height: float) -> None:
    """Completa las celdas vacías de las filas que tienen algún importe."""
    for table_row in table.rows:
        if not table_row.amounts:
            continue
        for column in range(len(table.column_x2)):
            if column not in table_row.amounts:
                amount = read_cell(image, table.cell_box(table_row, column, text_height),
                                   text_height)
                if amount is not None:
                    table_row.amounts[column] = amount
        table_row.amounts = dict(sorted(table_row.amounts.items()))


def page_paths(folder: Path, page: int) -> dict[str, Path]:
    stem = folder / f"page-{page:03d}"
    return {ext: stem.with_suffix(f".{ext}") for ext in ("png", "json", "txt")}


def ocr_page(pdf_path: Path, sha256: str, page: int, out_dir: Path) -> dict[str, Path]:
    """OCR de una página y guardado en out_dir/<sha256>/. Devuelve las rutas escritas."""
    folder = out_dir / sha256
    folder.mkdir(parents=True, exist_ok=True)
    image = render_page(pdf_path, page)
    observations = recognize(image)
    if not observations:
        raise OcrError(f"el OCR no encontró texto en la página {page} de {pdf_path.name}")
    paths = page_paths(folder, page)
    image.save(paths["png"])
    paths["json"].write_text(json.dumps({
        "source_file": pdf_path.name,
        "source_sha256": sha256,
        "page": page,
        "dpi": OCR_DPI,
        "engine": ENGINE,
        "languages": LANGUAGES,
        "image_size": image.size,
        "observations": [asdict(o) for o in observations],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    paths["txt"].write_text("\n".join(r.text for r in group_rows(observations)) + "\n",
                            encoding="utf-8")
    return paths


def text_height(observations: list[Observation]) -> float:
    return median(o.height for o in observations)


def load_page(folder: Path, page: int) -> tuple[list[Observation], Path]:
    paths = page_paths(folder, page)
    if not paths["json"].exists() or not paths["png"].exists():
        raise OcrError(f"falta el OCR de la página {page} en {folder}")
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    observations = [Observation(o["text"], o["confidence"], tuple(o["box"]))
                    for o in data["observations"]]
    return observations, paths["png"]


def crop_row(image_path: Path, row: Row, out_path: Path, padding: int = 4) -> Path:
    """Recorte PNG de una fila, de la etiqueta al último importe."""
    x1, y1, x2, y2 = row.box
    with Image.open(image_path) as image:
        box = (max(int(x1) - padding, 0), max(int(y1) - padding, 0),
               min(int(x2) + padding, image.width), min(int(y2) + padding, image.height))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.crop(box).save(out_path)
    return out_path
