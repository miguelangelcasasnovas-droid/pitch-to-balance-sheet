"""Motor de extracción: cifras por club con su página, fila, cuadres y recorte.

Cada club tiene su especificación en extract/clubs/<club>.py: páginas localizadas a mano mirando
la página, filas de cada tabla, relaciones de suma que tienen que cuadrar, y moneda y unidad
fijadas por el extractor.

Reglas:
- Un cuadre que no cuadra es un error. No se fuerza nada. La tolerancia es de redondeo:
  max(1, floor(0,5 × filas sumadas)), en la unidad del documento (sección 5 del plan), y un
  cuadre que pasa con diferencia lleva la marca "redondeo" y el número de filas.
- Un guion leído como cero solo vale si al menos un cuadre en el que interviene cuadra.
- Una celda vacía no es cero: si un cuadre o una cifra la necesita, es un error.
- Un control (otro documento del mismo club) tiene que dar las mismas cifras.
- Una cifra que solo está en una frase (sin tabla) se localiza por su frase; si el OCR la lee
  mal, la lectura en la imagen queda anotada en la cifra.
- En un paquete ESEF las cifras salen de hechos iXBRL (extract/ixbrl.py), citados por su
  etiqueta y su contexto; los cuadres usan los pesos del linkbase de cálculo del emisor.
"""

import html
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from PIL import Image

from pitch_to_balance_sheet.extract import ixbrl, ocr, pdf_text
from pitch_to_balance_sheet.extract.tables import (
    UNIT_HEADER,
    Amount,
    Row,
    Table,
    TableError,
    TableRow,
    group_rows,
    in_region,
    normalize_label,
    parse_amount,
    parse_decimal,
    read_tables,
)

# Si una indemnización está dentro de staff_costs: "true", "false" o "dudoso" (las cuentas no lo
# dicen). Vacío en los demás conceptos.
INCLUDED_IN_STAFF_COSTS = ("", "true", "false", "dudoso")


class ExtractionError(RuntimeError):
    """Falta una fila o una celda, un cuadre no cuadra o un control no coincide."""


@dataclass(frozen=True)
class Sum:
    """total = suma de las partes, en las columnas indicadas (todas si no se indican). Una parte
    con "-" delante se resta, p. ej. las bajas en un cuadro de movimientos."""

    total: str
    parts: tuple[str, ...]
    columns: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Cross:
    """Fila a fila: la columna total es la suma de las columnas parte."""

    total: str
    parts: tuple[str, ...]
    rows: tuple[str, ...]


@dataclass(frozen=True)
class Link:
    """La misma cifra en dos tablas, p. ej. el total de una nota y su línea en la cuenta.

    sign = -1 cuando una la da en positivo y la otra en negativo (un gasto en la nota y en la
    cuenta de resultados).
    """

    a: tuple[str, str, str]  # tabla, fila, columna
    b: tuple[str, str, str]
    sign: int = 1


@dataclass(frozen=True)
class LinkSum:
    """Una celda es la suma de celdas de otras tablas, p. ej. un total publicado en una nota y
    las líneas de la cuenta de resultados que lo forman."""

    total: tuple[str, str, str]  # tabla, fila, columna
    parts: tuple[tuple[str, str, str], ...]
    sign: int = 1  # -1 si el total va en negativo y las partes en positivo
    signs: tuple[int, ...] = ()  # signo de cada parte; vacío: todas suman


@dataclass(frozen=True)
class TableSpec:
    name: str
    page: int
    columns: tuple[str, ...]
    rows: dict[str, str]  # clave -> patrón del rótulo normalizado
    totals_after: dict[str, str] = field(default_factory=dict)  # total sin rótulo -> fila previa
    sums: tuple[Sum, ...] = ()
    cross: tuple[Cross, ...] = ()
    # Si el OCR no lee bien los rótulos: claves de las filas con cifras, en su orden. Tiene que
    # haber exactamente esas filas, y los rótulos de anchors tienen que coincidir.
    rows_by_order: tuple[str, ...] = ()
    anchors: dict[str, str] = field(default_factory=dict)
    # Filas con un rótulo que se repite en la página: clave -> patrón de la fila que va justo
    # antes (p. ej. "- Owners of the parent:" después de "... attributable to:").
    after: dict[str, str] = field(default_factory=dict)
    # Solo las filas de un bloque: desde la fila que casa con el primer patrón hasta la primera
    # que casa con el segundo, las dos incluidas. Para cuadros de movimientos con un bloque por
    # año ("Year ended 30 June 2025" ... "Closing book amount"). Varios tramos se aplican uno
    # dentro de otro.
    block: tuple | None = None
    select: str | None = None  # patrón de una fila que identifica la tabla en la página
    header_label: str | None = None  # patrón del resto de la fila de cabecera (p. ej. ^group$)
    region: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    header: str = UNIT_HEADER
    join_header_lines: bool = False  # cabeceras de columna en dos líneas (tables.read_tables)
    # Tabla cuya página no dice la unidad: la confirma un cuadre que pase contra esta otra tabla,
    # que sí la dice. Si no hay ese cuadre, error.
    unit_from: str | None = None
    # Quita las rayas de subtotal que el OCR lee como un guion: filas sin rótulo con un solo
    # guion y nada más. No son cifras de la tabla.
    drop_rules: bool = False


@dataclass(frozen=True)
class Part:
    """Una celda que entra en una cifra: se suma (sign=1) o se resta (sign=-1)."""

    table: str
    row: str
    column: str | None = None  # la de la cifra si no se indica
    sign: int = 1


@dataclass(frozen=True)
class FigureSpec:
    """Una cifra. Con una sola parte es la celda tal cual; con varias, o con alguna restada, es
    una cifra derivada (is_derived) y cada parte queda como componente con su fuente."""

    concept: str
    parts: tuple  # Part, o (tabla, fila) como atajo
    column: str
    note: str = ""  # observación sobre la definición
    # El informe da el gasto en negativo y aquí va en positivo: es un cambio de signo de
    # presentación, no una cifra derivada.
    negate: bool = False
    included_in_staff_costs: str = ""
    # Unidad de la cifra si no es la del club (p. ej. una nota en miles en un iXBRL en euros).
    unit: str | None = None
    # Un 0 derivado (un total menos todas sus líneas): si no da exactamente 0, es un error.
    expect_zero: bool = False

    def __post_init__(self):
        _check_included(self.concept, self.included_in_staff_costs)

    def resolved(self) -> tuple[Part, ...]:
        return tuple(p if isinstance(p, Part) else Part(*p) for p in self.parts)


@dataclass(frozen=True)
class SentenceFigureSpec:
    """Una cifra que solo se publica en una frase del texto, sin tabla.

    pattern se busca en el texto de cada línea de la página, sin distinguir mayúsculas, y su
    grupo "amount" es la cifra tal como se lee, con o sin símbolo de moneda delante. scale pasa
    de la unidad de la frase (p. ej. libras) a la del documento (miles); la división tiene que
    ser exacta. Si el OCR lee mal la cifra, image_reading es lo que se lee en la imagen de esa
    línea, y queda anotado en la cifra y en las correcciones.
    """

    concept: str
    page: int
    label: str  # cómo llama el informe a la partida
    pattern: str
    column: str
    scale: int = 1
    image_reading: str | None = None
    note: str = ""
    included_in_staff_costs: str = ""
    unit: str | None = None  # unidad de la cifra si no es la del club (p. ej. "shares")
    # Decimales de la cifra ("£210.8 million": 1). El valor queda en la unidad del último
    # decimal (2.108 décimas de millón, unit="hundred_thousands"): ver tables.parse_decimal.
    decimals: int = 0

    def __post_init__(self):
        _check_included(self.concept, self.included_in_staff_costs)


@dataclass(frozen=True)
class TextCellSpec:
    """Una cifra de una frase (del informe de gestión, por ejemplo) que se usa como una celda: en
    cuadres, cifras y partidas de ingresos. Se localiza por su texto, como una
    SentenceFigureSpec (decisión 45), y las de una misma página forman una tabla de una columna
    con ese nombre."""

    table: str
    key: str
    page: int
    label: str
    pattern: str
    column: str = "2025"
    scale: int = 1
    decimals: int = 0  # como en SentenceFigureSpec


def _check_included(concept: str, value: str) -> None:
    if value not in INCLUDED_IN_STAFF_COSTS:
        raise ValueError(f"{concept}: included_in_staff_costs={value!r}; tiene que ser uno de "
                         f"{INCLUDED_IN_STAFF_COSTS}")


@dataclass(frozen=True)
class DocumentSpec:
    method: str  # "ocr" o "text"
    tables: tuple[TableSpec, ...]
    figures: tuple[FigureSpec, ...]
    unit_evidence: str  # tiene que aparecer en el texto de cada página con tablas
    thousands: str = ","
    links: tuple[Link | LinkSum, ...] = ()
    control_index: int | None = None  # None: fuente principal; n: controls[n] de sources.yaml
    # "identical": el mismo documento en otra versión (traducción, otro depósito); sus cifras
    # tienen que coincidir. "restatement": el informe del año siguiente; se marca reexpresión si
    # una cifra difiere más de un 1% (sección 5 del plan), sin que sea un error.
    control_kind: str = "identical"
    # Si la especificación todavía no se puede escribir (p. ej. falta el PDF), el motivo.
    pending: str | None = None
    sentences: tuple[SentenceFigureSpec, ...] = ()
    # Solo en controles: conceptos de la fuente que este documento no trae, con el motivo.
    without: dict[str, str] = field(default_factory=dict)
    # Conceptos que el club no publica: hueco, con el motivo.
    gaps: dict[str, str] = field(default_factory=dict)
    text_cells: tuple[TextCellSpec, ...] = ()


@dataclass(frozen=True)
class XhtmlTableSpec:
    """Una tabla sin etiquetar del XHTML de un paquete ESEF (p. ej. una nota): se lee celda a
    celda y se cita por página y fila, como en un PDF."""

    name: str
    page: int
    columns: tuple[str, ...]
    cells: tuple[int, ...]  # índice de la celda de cada columna en la fila
    rows: dict[str, str]  # clave -> patrón del rótulo normalizado (la primera celda)
    select: str  # patrón de una fila que identifica la tabla en la página
    after: dict[str, str] = field(default_factory=dict)  # como en TableSpec
    block: tuple | None = None  # como en TableSpec
    sums: tuple[Sum, ...] = ()
    thousands: str = "."
    # Decimales de las cifras (p. ej. una tabla en millones con dos decimales): el valor queda en
    # la unidad del último decimal, como en SentenceFigureSpec.
    decimals: int = 0


@dataclass(frozen=True)
class Calc:
    """Cuadre de un documento iXBRL: total = suma de las partes por su peso (+1 o -1). Si el
    linkbase de cálculo del emisor tiene el arco, el peso tiene que ser el mismo."""

    total: str
    parts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class IxbrlDocumentSpec:
    """Un paquete ESEF: las cifras salen de hechos iXBRL, citados por su etiqueta y contexto."""

    entity: str  # identificador de la entidad en los contextos (el LEI)
    periods: dict[str, str]  # columna -> periodo del contexto, "2024-07-01/2025-06-30"
    unit: str  # unidad de los hechos, p. ej. "iso4217:EUR"
    concepts: dict[str, str]  # clave -> concepto iXBRL
    calcs: tuple[Calc, ...]
    figures: tuple[FigureSpec, ...]  # partes: ("ixbrl", clave); valores en la unidad del iXBRL
    # Perímetro: los contextos sin dimensiones, que en ESEF son las cuentas consolidadas.
    dimensions: tuple[tuple[str, str], ...] = ()
    method: str = "ixbrl"
    control_index: int | None = None
    control_kind: str = "identical"
    pending: str | None = None
    sentences: tuple[SentenceFigureSpec, ...] = ()
    without: dict[str, str] = field(default_factory=dict)
    gaps: dict[str, str] = field(default_factory=dict)
    tables: tuple[XhtmlTableSpec, ...] = ()  # notas sin etiquetar; partes: (tabla, fila)
    links: tuple[Link | LinkSum, ...] = ()
    # Conceptos de balance: hechos de un instante (la fecha de cierre), no de un periodo.
    instant_concepts: dict[str, str] = field(default_factory=dict)  # clave -> concepto iXBRL
    instants: dict[str, str] = field(default_factory=dict)  # columna -> "2025-06-30"
    thousands: str = "."  # separador de miles de las frases del XHTML


@dataclass(frozen=True)
class ClubSpec:
    club_id: str
    currency: str
    unit: str
    multiplier: int
    unit_basis: str  # de dónde salen la moneda y la unidad
    primary: DocumentSpec
    controls: tuple[DocumentSpec, ...] = ()


@dataclass(frozen=True)
class Check:
    document: str
    page: int
    relation: str
    column: str
    reported: int
    computed: int
    cells: tuple[tuple[str, str, str], ...] = ()
    rows: int = 1  # filas sumadas: de ellas depende la tolerancia

    @property
    def difference(self) -> int:
        return self.reported - self.computed

    @property
    def tolerance(self) -> int:
        """Cada fila redondeada puede desviarse ±0,5: max(1, floor(0,5 × filas))."""
        return max(1, self.rows // 2)

    @property
    def ok(self) -> bool:
        return abs(self.difference) <= self.tolerance

    @property
    def rounding(self) -> bool:
        """Cuadra, pero no exacto: la diferencia es de redondeo."""
        return self.ok and self.difference != 0

    @property
    def note(self) -> str:
        return (f"redondeo ({self.rows} {'fila' if self.rows == 1 else 'filas'})"
                if self.rounding else "")


@dataclass(frozen=True)
class Component:
    page: int
    label: str
    column: str
    sign: int
    amount: Amount
    row: object  # fila de la imagen (o hecho iXBRL), para el recorte
    image_path: Path | None
    reference: str = ""  # en iXBRL: etiqueta, contexto e id del hecho, en lugar de la fila


@dataclass(frozen=True)
class Figure:
    concept: str
    column: str
    value: int
    components: tuple[Component, ...]
    method: str
    note: str
    negated: bool = False
    included_in_staff_costs: str = ""
    unit: str | None = None  # si no es la del club

    @property
    def is_derived(self) -> bool:
        return len(self.components) > 1 or any(c.sign < 0 for c in self.components)

    @property
    def page(self) -> int:
        return self.components[0].page

    @property
    def label(self) -> str:
        text = ""
        for index, c in enumerate(self.components):
            operator = ("− " if c.sign < 0 else "") if index == 0 else (
                " − " if c.sign < 0 else " + ")
            text += operator + (c.label or "(total sin rótulo)")
        return text

    @property
    def sources(self) -> str:
        """Fuente de cada componente: página, fila, columna e importe."""
        return " ; ".join(
            f"{'−' if c.sign < 0 else '+'} {c.reference + ', ' if c.reference else ''}"
            f"pág. {c.page} {c.label or '(total sin rótulo)'!r} [{c.column}] {c.amount.value:,}"
            for c in self.components
        ) + (" (signo cambiado: el informe lo da en negativo)" if self.negated else "")

    @property
    def amounts(self) -> tuple[Amount, ...]:
        return tuple(c.amount for c in self.components)

    @property
    def ocr_note(self) -> str:
        return ocr_note(self.amounts, self.method)


@dataclass
class DocumentResult:
    name: str
    figures: list[Figure]
    checks: list[Check]
    corrections: list[str]
    summary: dict[str, int]  # recuento de correcciones por tipo, para las notas de OCR
    gaps: dict[str, str] = field(default_factory=dict)  # concepto -> motivo


@dataclass
class LoadedTable:
    spec: TableSpec
    table: Table
    rows: dict[str, TableRow]
    image_path: Path | None


def ocr_note(amounts: tuple[Amount, ...], method: str) -> str:
    if method == "ixbrl":  # sin OCR: se anota la escala de cada hecho
        return "iXBRL, sin OCR: " + "; ".join(dict.fromkeys(f for a in amounts for f in a.fixes))
    notes = []
    for amount in amounts:
        if amount.second_pass:
            notes.append("segunda lectura de la celda")
        elif amount.dash:
            notes.append("guion→cero" + (" (detectado en la imagen)" if amount.fixes else ""))
        elif amount.fixes:
            notes.append("corrección: " + "; ".join(amount.fixes))
    prefix = "OCR" if method == "ocr" else "texto del PDF, sin OCR"
    return f"{prefix}: " + (", ".join(dict.fromkeys(notes)) if notes else "sin corrección")


def _parse(raw: str, thousands: str, decimals: int = 0) -> Amount | None:
    return parse_decimal(raw, thousands, decimals) if decimals else parse_amount(raw, thousands)


def sentence_amount(rows: list[Row], spec: SentenceFigureSpec,
                    thousands: str) -> tuple[Amount, Row]:
    """La cifra de la frase, en la unidad del documento, y la línea donde está."""
    matches = [(row, m) for row in rows if (m := re.search(spec.pattern, row.text, re.I))]
    if len(matches) != 1:
        raise ExtractionError(f"pág. {spec.page}: la frase de {spec.concept} ({spec.pattern}) "
                              f"aparece {len(matches)} veces")
    row, match = matches[0]
    raw = match.group("amount")
    # "£nil" en el texto: el informe dice que es cero.
    ocr_read = (Amount(0, raw, ("«nil» en el texto: cero",)) if raw.strip().lower() == "nil"
                else _parse(raw.lstrip("£€$"), thousands, spec.decimals))
    if spec.image_reading is None:
        read = ocr_read
        if read is None or read.dash:
            raise ExtractionError(
                f"pág. {spec.page}: {spec.concept}: {raw!r} no es un importe. Si el OCR lo lee "
                "mal, hay que leerlo en la imagen y anotarlo en image_reading")
    else:
        read = _parse(spec.image_reading.lstrip("£€$"), thousands, spec.decimals)
        if read is None or read.dash:
            raise ExtractionError(f"pág. {spec.page}: {spec.concept}: la lectura en la imagen "
                                  f"{spec.image_reading!r} no es un importe")
        if ocr_read is not None and ocr_read.value == read.value:
            raise ExtractionError(
                f"pág. {spec.page}: {spec.concept}: el OCR ya lee {raw!r}; sobra image_reading")
    if read.value % spec.scale:
        raise ExtractionError(f"pág. {spec.page}: {spec.concept}: {read.value:,} no es múltiplo "
                              f"exacto de {spec.scale:,}")
    fixes = read.fixes
    if spec.image_reading is not None:
        fixes = (f"cifra leída en la imagen ({spec.image_reading}) porque el OCR falló "
                 f"(lee {raw!r})", *fixes)
    return Amount(read.value // spec.scale, raw, fixes), row


def find_rows(table: Table, patterns: dict[str, str], page: int) -> dict[str, TableRow]:
    found = {}
    for key, pattern in patterns.items():
        matches = [r for r in table.rows if re.search(pattern, r.label)]
        if len(matches) != 1:
            raise ExtractionError(
                f"pág. {page}: la fila {key} ({pattern}) aparece {len(matches)} veces"
            )
        if matches[0].conflict:
            raise ExtractionError(f"pág. {page}: fila {key}: {matches[0].conflict}")
        found[key] = matches[0]
    return found


def rows_by_order(table: Table, keys: tuple[str, ...], anchors: dict[str, str],
                  page: int) -> dict[str, TableRow]:
    """Asigna las claves, en orden, a las filas de la tabla que tienen cifras."""
    numeric = [row for row in table.rows if row.amounts or row.conflict]
    if len(numeric) != len(keys):
        raise ExtractionError(f"pág. {page}: se esperaban {len(keys)} filas con cifras y hay "
                              f"{len(numeric)}")
    found = dict(zip(keys, numeric, strict=True))
    for key, row in found.items():
        if row.conflict:
            raise ExtractionError(f"pág. {page}: fila {key}: {row.conflict}")
    for key, pattern in anchors.items():
        if not re.search(pattern, found[key].label):
            raise ExtractionError(f"pág. {page}: la fila {key} dice {found[key].raw_label!r}, "
                                  f"que no casa con {pattern}")
    return found


def _is_rule(row: TableRow) -> bool:
    """Una raya de subtotal leída como guion: sin rótulo, con un solo guion y nada más."""
    return (not row.label and len(row.amounts) == 1
            and all(amount.dash for amount in row.amounts.values()))


def block_rows(table: Table, block: tuple | None, page: int) -> Table:
    """La tabla reducida a las filas de un bloque (ver TableSpec.block)."""
    if block is None:
        return table
    for start, end in ((block,) if isinstance(block[0], str) else block):
        starts = [index for index, row in enumerate(table.rows) if re.search(start, row.label)]
        if len(starts) != 1:
            raise ExtractionError(f"pág. {page}: el inicio del bloque ({start}) aparece "
                                  f"{len(starts)} veces")
        ends = [index for index, row in enumerate(table.rows)
                if index > starts[0] and re.search(end, row.label)]
        if not ends:
            raise ExtractionError(f"pág. {page}: el bloque que empieza en {start} no acaba en "
                                  f"{end}")
        table = Table(table.header_raw, table.column_x2, table.rows[starts[0]:ends[0] + 1],
                      table.header_label)
    return table


def row_after(table: Table, anchor: str, pattern: str, key: str, page: int) -> TableRow:
    """La fila que va justo después de la fila ancla, para rótulos que se repiten."""
    anchors = [index for index, row in enumerate(table.rows) if re.search(anchor, row.label)]
    if len(anchors) != 1:
        raise ExtractionError(f"pág. {page}: el ancla de {key} ({anchor}) aparece "
                              f"{len(anchors)} veces")
    index = anchors[0] + 1
    if index >= len(table.rows) or not re.search(pattern, table.rows[index].label):
        found = table.rows[index].raw_label if index < len(table.rows) else "nada"
        raise ExtractionError(f"pág. {page}: después de {anchor} viene {found!r}, que no casa "
                              f"con la fila {key} ({pattern})")
    if table.rows[index].conflict:
        raise ExtractionError(f"pág. {page}: fila {key}: {table.rows[index].conflict}")
    return table.rows[index]


def total_after(table: Table, last: TableRow, page: int) -> TableRow:
    """La fila de total sin rótulo que va justo después de la última partida."""
    index = table.rows.index(last) + 1
    if index >= len(table.rows) or table.rows[index].label or not table.rows[index].amounts:
        raise ExtractionError(f"pág. {page}: no hay fila de total después de {last.raw_label!r}")
    return table.rows[index]


def _amount(loaded: dict[str, LoadedTable], cell: tuple[str, str, str]) -> Amount:
    table_name, row_key, column = cell
    item = loaded[table_name]
    index = item.spec.columns.index(column)
    amount = item.rows[row_key].amounts.get(index)
    if amount is None:
        raise ExtractionError(
            f"pág. {item.spec.page}: la fila {row_key} no tiene importe en la columna {column}"
        )
    return amount


def _checks(document: str, loaded: dict[str, LoadedTable], links: tuple[Link, ...]):
    checks = []
    for name, item in loaded.items():
        page = item.spec.page
        for rule in item.spec.sums:
            signs = [-1 if key.startswith("-") else 1 for key in rule.parts]
            keys = [key.removeprefix("-") for key in rule.parts]
            relation = f"{rule.total} = " + "".join(
                ("− " if sign < 0 else "") + key if index == 0
                else (" − " if sign < 0 else " + ") + key
                for index, (sign, key) in enumerate(zip(signs, keys, strict=True)))
            for column in rule.columns or item.spec.columns:
                cells = tuple((name, key, column) for key in (rule.total, *keys))
                checks.append(Check(
                    document, page, relation, column, _amount(loaded, cells[0]).value,
                    sum(sign * _amount(loaded, cell).value
                        for sign, cell in zip(signs, cells[1:], strict=True)),
                    cells, len(rule.parts)))
        for rule in item.spec.cross:
            for key in rule.rows:
                cells = tuple((name, key, column) for column in (rule.total, *rule.parts))
                checks.append(Check(
                    document, page, f"{key}: {rule.total} = " + " + ".join(rule.parts),
                    rule.total, _amount(loaded, cells[0]).value,
                    sum(_amount(loaded, cell).value for cell in cells[1:]), cells,
                    len(rule.parts)))
    for link in links:
        if isinstance(link, LinkSum):
            signs = link.signs or (1,) * len(link.parts)
            parts = "".join(("" if index == 0 and sign > 0 else " − " if sign < 0 else " + ")
                            + ".".join(part)
                            for index, (sign, part) in enumerate(zip(signs, link.parts,
                                                                     strict=True)))
            checks.append(Check(
                document, loaded[link.total[0]].spec.page,
                f"{'.'.join(link.total)} = " + (f"-({parts})" if link.sign < 0 else parts),
                link.total[2], _amount(loaded, link.total).value,
                link.sign * sum(sign * _amount(loaded, part).value
                                for sign, part in zip(signs, link.parts, strict=True)),
                (link.total, *link.parts), len(link.parts)))
            continue
        checks.append(Check(
            document, loaded[link.a[0]].spec.page,
            f"{'.'.join(link.a)} = {'-' if link.sign < 0 else ''}{'.'.join(link.b)}",
            link.a[2], _amount(loaded, link.a).value, link.sign * _amount(loaded, link.b).value,
            (link.a, link.b)))
    return checks


def _corrections(loaded: dict[str, LoadedTable]) -> tuple[list[str], dict[str, int]]:
    """Lo que hubo que corregir o completar en las filas usadas, y su recuento por tipo."""
    notes, summary = [], {}

    def count(kind: str, n: int = 1) -> None:
        summary[kind] = summary.get(kind, 0) + n

    for item in loaded.values():
        misread = [h for h in item.table.header_raw
                   if re.fullmatch(UNIT_HEADER, h) and not h.startswith("£")]
        if misread:
            count("cabeceras £ leídas como otra letra", len(misread))
            notes.append(f"pág. {item.spec.page}: {len(misread)} de {len(item.table.header_raw)} "
                         f"cabeceras £ leídas como {', '.join(sorted(set(misread)))}")
        for key, row in item.rows.items():
            for index, amount in row.amounts.items():
                if not (amount.fixes or amount.second_pass):
                    continue
                if amount.second_pass:
                    count("segundas lecturas de celda")
                elif amount.dash:
                    count("guiones→cero detectados en la imagen")
                else:
                    for fix in amount.fixes:
                        count(fix)
                notes.append(f"pág. {item.spec.page} {key} [{item.spec.columns[index]}]: "
                             f"{amount.raw!r} -> {amount.value:,} ({'; '.join(amount.fixes)})")
    return notes, summary


def _page(method: str, pdf_path: Path, sha256: str, page: int, interim: Path, region,
          reocr: bool):
    """Palabras y la imagen de una página. En los documentos con OCR se lee el OCR guardado en
    data/interim/ocr/<sha256>/; Vision solo se vuelve a pasar con reocr (--reocr)."""
    if method == "ocr":
        folder = interim / "ocr" / sha256
        if reocr:
            ocr.ocr_page(pdf_path, sha256, page, interim / "ocr", region)
        elif not ocr.page_paths(folder, page, region)["json"].exists():
            raise ExtractionError(
                f"pág. {page}: no hay OCR guardado en {folder}. Para pasar Vision, ejecuta con "
                "--reocr"
            )
        return ocr.load_page(folder, page, region)
    return (pdf_text.page_observations(pdf_path, page),
            pdf_text.page_image(pdf_path, sha256, page, interim / "text"))


def _text_tables(spec: DocumentSpec) -> dict[str, list[TextCellSpec]]:
    tables: dict[str, list[TextCellSpec]] = {}
    for cell in spec.text_cells:
        tables.setdefault(cell.table, []).append(cell)
    for table, cells in tables.items():
        if len({cell.page for cell in cells}) != 1:
            raise ExtractionError(f"las frases de {table} tienen que ser de una sola página")
    return tables


def _text_table(spec: DocumentSpec, name: str, cells: list[TextCellSpec], pdf_path: Path,
                sha256: str, interim: Path, reocr: bool) -> LoadedTable:
    """Las frases de una página como una tabla de una columna: una fila por frase."""
    page = cells[0].page
    observations, image_path = _page(spec.method, pdf_path, sha256, page, interim,
                                     ocr.FULL_PAGE, reocr)
    rows = group_rows(observations)
    found = {}
    for cell in cells:
        sentence = SentenceFigureSpec(cell.key, page, cell.label, cell.pattern, cell.column,
                                      scale=cell.scale, decimals=cell.decimals)
        amount, row = sentence_amount(rows, sentence, spec.thousands)
        found[cell.key] = TableRow(normalize_label(cell.label), cell.label, None, {0: amount},
                                   row)
    columns = tuple(dict.fromkeys(cell.column for cell in cells))
    if len(columns) != 1:
        raise ExtractionError(f"las frases de {name} tienen que ser de una sola columna")
    table_spec = TableSpec(name, page, columns, {key: "" for key in found})
    return LoadedTable(table_spec, Table((), (), list(found.values())), found, image_path)


def _exact(value: Decimal) -> int | Decimal:
    """Entero si lo es; si no, el decimal exacto (sin redondear)."""
    return int(value) if value == value.to_integral_value() else value


def read_ixbrl_document(name: str, spec: IxbrlDocumentSpec, path: Path) -> DocumentResult:
    """Cifras y cuadres de un paquete ESEF, en la unidad del iXBRL (euros), tal como están
    etiquetados: value_reported es el valor exacto (sección 5 del plan)."""
    both = set(spec.concepts) & set(spec.instant_concepts)
    if both:
        raise ExtractionError(f"{', '.join(sorted(both))}: clave de periodo y de instante a la vez")
    concepts = {**spec.concepts, **spec.instant_concepts}
    try:
        report = ixbrl.read_report(path)
        facts = {(key, column): report.find(concept, spec.entity, period, spec.dimensions)
                 for mapping, periods in ((spec.concepts, spec.periods),
                                          (spec.instant_concepts, spec.instants))
                 for key, concept in mapping.items()
                 for column, period in periods.items()}
    except ixbrl.IxbrlError as exc:
        raise ExtractionError(str(exc)) from exc
    for fact in facts.values():
        if fact.unit != spec.unit:
            raise ExtractionError(f"{fact.concept} ({fact.id}) está en {fact.unit}, no en "
                                  f"{spec.unit}")

    checks = []
    for calc in spec.calcs:
        terms = []
        for key, weight in calc.parts:
            arc = (ixbrl.concept_key(concepts[calc.total]), ixbrl.concept_key(concepts[key]))
            declared = report.calculations.get(arc)
            if declared is not None and declared != weight:
                raise ExtractionError(
                    f"{calc.total}: {key} va con peso {weight:+d} y el linkbase de cálculo del "
                    f"emisor le da {declared:+}")
            terms.append(f"{'−' if weight < 0 else '+'} {key}"
                         + ("" if declared is not None else " (sin arco en el linkbase)"))
        relation = f"{calc.total} = " + " ".join(terms).removeprefix("+ ")
        for column in (spec.instants if calc.total in spec.instant_concepts else spec.periods):
            total = facts[(calc.total, column)]
            computed = sum(weight * facts[(key, column)].value for key, weight in calc.parts)
            cells = tuple(("ixbrl", key, column) for key in (calc.total, *dict(calc.parts)))
            checks.append(Check(name, total.page, relation, column, _exact(total.value),
                                _exact(computed), cells, len(calc.parts)))

    loaded = {table_spec.name: _xhtml_table(report, table_spec) for table_spec in spec.tables}
    checks += _checks(name, loaded, spec.links)

    figures = []
    for figure_spec in spec.figures:
        components = []
        for part in figure_spec.resolved():
            column = part.column or figure_spec.column
            if part.table != "ixbrl":  # nota sin etiquetar
                item = loaded[part.table]
                row = item.rows[part.row]
                amount = _amount(loaded, (part.table, part.row, column))
                components.append(Component(
                    item.spec.page, row.raw_label, column, part.sign,
                    Amount(amount.value, amount.raw,
                           ("celda de una tabla sin etiquetar del XHTML", *amount.fixes)),
                    row.row, None, reference=f"tabla sin etiquetar del XHTML, columna {column}"))
                continue
            fact = facts[(part.row, column)]
            value = _exact(fact.value)
            scale_note = (f"{fact.unit} con scale {fact.scale} y decimals {fact.decimals}: "
                          "valor exacto, en unidades")
            period = fact.context.period.replace("/", "–")
            components.append(Component(
                fact.page, fact.label, column, part.sign, Amount(value, fact.raw, (scale_note,)),
                fact, None,
                reference=f"{fact.concept} [contexto {fact.context.id}, {period}, sin "
                          f"dimensiones; hecho {fact.id}]"))
        if len({isinstance(c.row, ixbrl.Fact) for c in components}) > 1:
            raise ExtractionError(f"{figure_spec.concept} mezcla hechos etiquetados y celdas de "
                                  "notas sin etiquetar, que van en otra unidad")
        value = sum(c.sign * c.amount.value for c in components)
        figures.append(Figure(
            figure_spec.concept, figure_spec.column, -value if figure_spec.negate else value,
            tuple(components), "ixbrl", figure_spec.note, figure_spec.negate,
            figure_spec.included_in_staff_costs, figure_spec.unit))
    figures += [_xhtml_sentence(report, sentence, spec.thousands) for sentence in spec.sentences]
    return DocumentResult(name, figures, checks, [], {}, _gaps(spec, figures))


def _xhtml_sentence(report: ixbrl.Report, spec: SentenceFigureSpec, thousands: str) -> Figure:
    """Una cifra que solo está en una frase del XHTML, sin etiquetar: se localiza por su texto
    en la página, como en un PDF (decisión 45), y se cita por página."""
    text = report.texts.get(spec.page, "")
    matches = list(re.finditer(spec.pattern, text, re.I))
    if len(matches) != 1:
        raise ExtractionError(f"pág. {spec.page} del XHTML: la frase de {spec.concept} "
                              f"({spec.pattern}) aparece {len(matches)} veces")
    match = matches[0]
    raw = match.group("amount")
    amount = _parse(raw, thousands, spec.decimals)
    if amount is None or amount.dash:
        raise ExtractionError(f"pág. {spec.page} del XHTML: {spec.concept}: {raw!r} no es un "
                              "importe")
    if amount.value % spec.scale:
        raise ExtractionError(f"pág. {spec.page} del XHTML: {spec.concept}: {amount.value:,} no "
                              f"es múltiplo exacto de {spec.scale:,}")
    snippet = text[max(match.start() - 250, 0):match.end() + 250]
    component = Component(
        spec.page, spec.label, spec.column, 1,
        Amount(amount.value // spec.scale, raw, ("frase del XHTML, sin etiquetar",)),
        f"<tr><td>…{html.escape(snippet)}…</td></tr>", None,
        reference="frase del XHTML, sin etiquetar")
    return Figure(spec.concept, spec.column, component.amount.value, (component,), "ixbrl",
                  spec.note, unit=spec.unit)


def _gaps(spec, figures: list[Figure]) -> dict[str, str]:
    """Los huecos del documento: un concepto no puede ser a la vez hueco y cifra."""
    both = set(spec.gaps) & {figure.concept for figure in figures}
    if both:
        raise ExtractionError(f"{', '.join(sorted(both))}: hueco y cifra a la vez")
    return dict(spec.gaps)


def _xhtml_table(report: ixbrl.Report, spec: XhtmlTableSpec) -> LoadedTable:
    """Una tabla sin etiquetar del XHTML como tabla del motor: primera celda = rótulo."""
    candidates = [rows for rows in report.tables.get(spec.page, ())
                  if any(row.cells and re.search(spec.select, normalize_label(row.cells[0]))
                         for row in rows)]
    if len(candidates) != 1:
        raise ExtractionError(f"pág. {spec.page} del XHTML: se esperaba una tabla {spec.name} "
                              f"({spec.select}) y hay {len(candidates)}")
    table_rows = []
    for row in candidates[0]:
        if not row.cells:
            continue
        amounts = {}
        for index, cell in enumerate(spec.cells):
            text = row.cells[cell] if cell < len(row.cells) else ""
            amount = _parse(text, spec.thousands, spec.decimals) if text.strip() else None
            if amount is not None:
                amounts[index] = amount
        table_rows.append(TableRow(normalize_label(row.cells[0]), row.cells[0], None, amounts,
                                   row.html))
    table = block_rows(Table((), (), table_rows), spec.block, spec.page)
    rows = find_rows(table, {key: pattern for key, pattern in spec.rows.items()
                             if key not in spec.after}, spec.page)
    for key, anchor in spec.after.items():
        rows[key] = row_after(table, anchor, spec.rows[key], key, spec.page)
    table_spec = TableSpec(spec.name, spec.page, spec.columns, spec.rows, sums=spec.sums)
    return LoadedTable(table_spec, table, rows, None)


def read_document(name: str, spec: DocumentSpec, pdf_path: Path, sha256: str,
                  interim: Path, reocr: bool = False) -> DocumentResult:
    if spec.pending:
        raise ExtractionError(spec.pending)
    if spec.method == "ixbrl":
        return read_ixbrl_document(name, spec, pdf_path)
    loaded: dict[str, LoadedTable] = {}
    for table_spec in spec.tables:
        page = table_spec.page
        observations, image_path = _page(spec.method, pdf_path, sha256, page, interim,
                                         table_spec.region, reocr)
        if table_spec.unit_from is None and not re.search(
                spec.unit_evidence, " ".join(o.text for o in observations), re.I):
            raise ExtractionError(f"pág. {page}: no aparece {spec.unit_evidence!r}, así que no "
                                  "se puede confirmar la unidad")
        with Image.open(image_path) as image:
            region = in_region(observations, table_spec.region, image.width, image.height)
            try:
                candidates = read_tables(group_rows(region), table_spec.header, spec.thousands,
                                         table_spec.join_header_lines)
            except TableError as exc:
                raise ExtractionError(f"pág. {page}: {exc}") from exc
            candidates = [t for t in candidates if len(t.column_x2) == len(table_spec.columns)]
            if table_spec.select:
                candidates = [t for t in candidates
                              if any(re.search(table_spec.select, r.label) for r in t.rows)]
            if table_spec.header_label:
                candidates = [t for t in candidates
                              if re.search(table_spec.header_label, t.header_label)]
            if len(candidates) != 1:
                raise ExtractionError(
                    f"pág. {page}: se esperaba una tabla {table_spec.name} de "
                    f"{len(table_spec.columns)} columnas y hay {len(candidates)} tablas así"
                )
            table = block_rows(candidates[0], table_spec.block, page)
            if table_spec.drop_rules:
                table = Table(table.header_raw, table.column_x2,
                              [row for row in table.rows if not _is_rule(row)],
                              table.header_label)
            rows = find_rows(table, {key: pattern for key, pattern in table_spec.rows.items()
                                     if key not in table_spec.after}, page)
            for key, anchor in table_spec.after.items():
                rows[key] = row_after(table, anchor, table_spec.rows[key], key, page)
            if table_spec.rows_by_order:
                rows |= rows_by_order(table, table_spec.rows_by_order, table_spec.anchors, page)
            for key, previous in table_spec.totals_after.items():
                rows[key] = total_after(table, rows[previous], page)
            reader = None
            if spec.method == "ocr":
                cells_path = ocr.page_paths(interim / "ocr" / sha256, page,
                                            table_spec.region)["cells"]
                reader = ocr.CellReader(cells_path, allow_vision=reocr)
            try:  # solo las filas que se usan: el resto de la página puede ser texto corrido
                ocr.fill_missing_cells(table, image, ocr.text_height(region),
                                       allow_ocr=spec.method == "ocr", rows=list(rows.values()),
                                       reader=reader)
            except ocr.OcrError as exc:
                raise ExtractionError(f"pág. {page}: {exc}") from exc
        loaded[table_spec.name] = LoadedTable(table_spec, table, rows, image_path)

    for table, cells in _text_tables(spec).items():
        loaded[table] = _text_table(spec, table, cells, pdf_path, sha256, interim, reocr)
    checks = _checks(name, loaded, spec.links)
    for table_spec in spec.tables:
        if table_spec.unit_from and not any(
                check.ok and {cell[0] for cell in check.cells} >= {table_spec.name,
                                                                   table_spec.unit_from}
                for check in checks):
            raise ExtractionError(
                f"pág. {table_spec.page}: no dice la unidad y ningún cuadre la une con la tabla "
                f"{table_spec.unit_from}, que sí la dice")
    figures = []
    figure_cells = set()
    for figure_spec in spec.figures:
        components = []
        for part in figure_spec.resolved():
            column = part.column or figure_spec.column
            cell = (part.table, part.row, column)
            figure_cells.add(cell)
            item = loaded[part.table]
            row = item.rows[part.row]
            components.append(Component(item.spec.page, row.raw_label, column, part.sign,
                                        _amount(loaded, cell), row.row, item.image_path))
        value = sum(c.sign * c.amount.value for c in components)
        if figure_spec.expect_zero and value != 0:
            raise ExtractionError(
                f"{figure_spec.concept} tendría que ser 0 (el total menos todas sus líneas) y da "
                f"{value:,}: " + "; ".join(f"{'−' if c.sign < 0 else '+'} pág. {c.page} "
                                           f"{c.label!r} {c.amount.value:,}" for c in components))
        figures.append(Figure(
            figure_spec.concept, figure_spec.column, -value if figure_spec.negate else value,
            tuple(components), spec.method, figure_spec.note, figure_spec.negate,
            figure_spec.included_in_staff_costs, figure_spec.unit))

    covered = {cell for check in checks if check.ok for cell in check.cells}
    used = {cell for check in checks for cell in check.cells} | figure_cells
    for cell in sorted(used):
        if _amount(loaded, cell).dash and cell not in covered:
            failing = [check for check in checks if cell in check.cells and not check.ok]
            reason = "ningún cuadre lo respalda" if not failing else (
                "el cuadre que lo contiene no cuadra: " + "; ".join(
                    f"{c.relation} [{c.column}] {c.reported:,} frente a {c.computed:,} "
                    f"(diferencia {c.difference:,})" for c in failing))
            raise ExtractionError(f"pág. {loaded[cell[0]].spec.page}: el guion de {cell[1]} "
                                  f"[{cell[2]}] se leyó como cero y {reason}")

    notes, summary = _corrections(loaded)
    for sentence in spec.sentences:
        observations, image_path = _page(spec.method, pdf_path, sha256, sentence.page, interim,
                                         ocr.FULL_PAGE, reocr)
        amount, row = sentence_amount(group_rows(observations), sentence, spec.thousands)
        figures.append(Figure(
            sentence.concept, sentence.column, amount.value,
            (Component(sentence.page, sentence.label, sentence.column, 1, amount, row,
                       image_path),),
            spec.method, sentence.note, included_in_staff_costs=sentence.included_in_staff_costs,
            unit=sentence.unit))
        if sentence.image_reading is not None:
            summary["cifras leídas en la imagen porque el OCR falló"] = summary.get(
                "cifras leídas en la imagen porque el OCR falló", 0) + 1
        if amount.fixes:
            notes.append(f"pág. {sentence.page} {sentence.concept}: {amount.raw!r} -> "
                         f"{amount.value:,} ({'; '.join(amount.fixes)})")
    return DocumentResult(name, figures, checks, notes, summary, _gaps(spec, figures))
