"""Lectura de tablas de cuentas a partir de palabras con posición.

Sirve igual para lo que devuelve el OCR que para el texto de un PDF: cada palabra es una
Observation con su caja en píxeles de la página renderizada a 300 ppp.

- Las filas se forman con las palabras cuyo centro vertical está a menos de media altura.
- Una tabla empieza en una fila de cabecera (p. ej. "£'000" o "2024/2025") y cada importe va a la
  columna cuya cabecera tiene el borde derecho más cerca.
- parse_amount convierte un importe en entero y anota lo que ha tenido que corregir.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from statistics import median

# Cabecera de miles: "£'000", "£000" y cómo lo lee a veces el OCR ("€'000", "f'000", "$'000",
# "2'000", "·'000", "'000"...). Si el primer carácter es un dígito, tiene que ir el apóstrofo,
# para no confundir la cabecera con un año o una cifra. La moneda no se toma de aquí.
UNIT_HEADER = r"^([^\s\d]?[’'‘`´]?|\d[’'‘`´])[0O]{3}$"
# Lo mismo dentro de un texto: se exige en cada página que se lee por OCR.
THOUSANDS_EVIDENCE = r"(^|\s)([^\s\d]?[’'‘`´]?|\d[’'‘`´])[0O]{3}(\s|$)"
DASHES = {"-", "–", "—", "_"}
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5"})


class TableError(RuntimeError):
    """Una tabla no se puede leer como se esperaba."""


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
    confidence: float


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
                                    x1 + width * match.end(), observation.confidence))
        return result


@dataclass(frozen=True)
class Amount:
    value: int
    raw: str
    fixes: tuple[str, ...] = ()
    confidence: float | None = None
    dash: bool = False  # un guion leído como cero
    second_pass: bool = False  # leída en una segunda pasada de OCR solo sobre la celda


@dataclass
class TableRow:
    label: str  # rótulo normalizado: minúsculas, sin acentos ni apóstrofos
    raw_label: str
    note: str | None
    amounts: dict[int, Amount]  # índice de columna -> importe
    row: Row
    conflict: str | None = None  # la fila no se pudo leer; solo es un error si se usa


@dataclass
class Table:
    header_raw: tuple[str, ...]  # las cabeceras de columna tal como se leyeron
    column_x2: tuple[float, ...]
    rows: list[TableRow]
    header_label: str = ""  # el resto de la fila de cabecera, normalizado (p. ej. "group")

    def cell_box(self, table_row: TableRow, column: int, text_height: float):
        """Caja de una celda: junto al borde derecho de su columna, en la banda de su fila.

        Las cifras van alineadas a la derecha, y el paréntesis de cierre sobresale un poco. La
        banda no llega a la mitad de la distancia a la fila de arriba ni a la de abajo, para no
        leer una cifra de la fila vecina.
        """
        gaps = [b - a for a, b in zip(self.column_x2, self.column_x2[1:], strict=False)]
        width = min(gaps) if gaps else 4 * text_height
        x2 = self.column_x2[column]
        centers = [(r.row.box[1] + r.row.box[3]) / 2 for r in self.rows]
        index = self.rows.index(table_row)
        center_y = centers[index]
        up = 0.45 * (center_y - centers[index - 1]) if index > 0 else text_height
        down = 0.45 * (centers[index + 1] - center_y) if index + 1 < len(centers) else text_height
        return (int(x2 - 0.8 * width), int(center_y - min(0.55 * text_height, up)),
                int(x2 + 0.12 * width), int(center_y + min(0.55 * text_height, down)))


def amount_pattern(thousands: str) -> re.Pattern:
    return re.compile(r"^\(?\d{1,3}(" + re.escape(thousands) + r"\d{3})*\)?$")


def parse_amount(raw: str, thousands: str = ",") -> Amount | None:
    """Importe tal como se leyó -> entero. None si no parece un importe."""
    text = raw.strip().replace(" ", "")
    if text in DASHES:
        return Amount(0, raw, dash=True)
    if text[:1] in ("-", "−") and amount_pattern(thousands).fullmatch(text[1:]) \
            and not text[1:].startswith("("):
        # Negativo con signo menos delante, como en las cuentas de Dortmund ("-27,359").
        positive = parse_amount(text[1:], thousands)
        return Amount(-positive.value, raw, positive.fixes)
    pattern = amount_pattern(thousands)
    other = "." if thousands == "," else ","
    fixes = []
    if re.search(r"\d", text) and re.search(r"[OolIS]", text):
        text = text.translate(DIGIT_LOOKALIKES)
        fixes.append("letra leída en lugar de dígito")
    if thousands == "," and re.fullmatch(r"\(?\d{1,3}([,;]\d{3})*;\d{3}([,;]\d{3})*\)?", text):
        text = text.replace(";", ",")
        fixes.append("punto y coma en lugar de coma de miles")
    if re.fullmatch(r"\(?\d{1,3}(" + re.escape(other) + r"\d{3})+\)?", text):
        text = text.replace(other, thousands)
        fixes.append(f"{'punto' if other == '.' else 'coma'} en lugar de separador de miles")
    if text.startswith("(") != text.endswith(")") and pattern.fullmatch(f"({text.strip('()')})"):
        text = f"({text.strip('()')})"
        fixes.append("paréntesis sin pareja")
    if not pattern.fullmatch(text):
        return None
    value = int(text.strip("()").replace(thousands, ""))
    return Amount(-value if text.startswith("(") else value, raw, tuple(fixes))


def normalize_label(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("ß", "ss"))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[’'‘`´]", "", text)
    text = re.sub(r"\.{2,}", " ", text)  # puntos de relleno: "Revenue ........ 4 666,514"
    text = re.sub(r"[^a-z0-9()/&,\-. ]", " ", text)
    return " ".join(text.split())


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


def in_region(observations: list[Observation], region, width: float, height: float):
    """Las observaciones cuyo centro cae en la región (fracciones x1, y1, x2, y2 de la página)."""
    x1, y1, x2, y2 = region[0] * width, region[1] * height, region[2] * width, region[3] * height
    return [o for o in observations
            if x1 <= (o.box[0] + o.box[2]) / 2 <= x2 and y1 <= o.center_y <= y2]


def _touching(tokens: list[Token]) -> list[Token]:
    """Une los trozos de una palabra espaciada letra a letra: pdfplumber lee "2024/2025" con
    las letras separadas como "2 0 2 4 /2 0 2 5", con trozos que se tocan. Dos palabras de
    verdad llevan un espacio entre medias y no se unen."""
    joined: list[Token] = []
    for token in tokens:
        if joined:
            previous = joined[-1]
            char = (previous.x2 - previous.x1) / max(len(previous.text), 1)
            if token.x1 - previous.x2 <= 0.25 * char:
                joined[-1] = Token(previous.text + token.text, previous.x1, token.x2,
                                   min(previous.confidence, token.confidence))
                continue
        joined.append(token)
    return joined


def read_tables(rows: list[Row], header: str = UNIT_HEADER, thousands: str = ",",
                join_header_lines: bool = False) -> list[Table]:
    """Tablas de la página: cada una empieza en una fila con cabeceras de columna.

    Con join_header_lines, una fila que solo tiene cabeceras y va justo después de otra fila de
    cabecera se une a ella: cabeceras en dos líneas, como "Segm. A ... Total" con "serviços"
    debajo de "Outros".
    """
    header_pattern = re.compile(header, re.IGNORECASE)
    tables: list[Table] = []
    skip = False
    for index, row in enumerate(rows):
        if skip:
            skip = False
            continue
        tokens = _touching(row.tokens())
        headers = [token for token in tokens if header_pattern.fullmatch(token.text)]
        following = _touching(rows[index + 1].tokens()) if index + 1 < len(rows) else []
        if (headers and join_header_lines and following
                and all(header_pattern.fullmatch(token.text) for token in following)):
            tokens = sorted(tokens + following, key=lambda token: token.x2)
            headers = [token for token in tokens if header_pattern.fullmatch(token.text)]
            skip = True
        if headers:
            label = " ".join(t.text for t in tokens if not header_pattern.fullmatch(t.text))
            tables.append(Table(tuple(t.text for t in headers), tuple(t.x2 for t in headers), [],
                                normalize_label(label)))
            continue
        if tables:
            table_row = _table_row(row, tables[-1].column_x2, thousands)
            previous = tables[-1].rows[-1] if tables[-1].rows else None
            # Rótulo en dos líneas con las cifras en la segunda ("Turnover of the Group
            # including its share of" / "joint ventures 691,572 ..."): se unen los rótulos. La
            # fila sigue siendo la de las cifras.
            if (previous is not None and not previous.amounts and not previous.conflict
                    and previous.raw_label and (table_row.amounts or table_row.conflict)
                    and table_row.raw_label[:1].islower()):
                table_row.raw_label = f"{previous.raw_label} {table_row.raw_label}"
                table_row.label = normalize_label(table_row.raw_label)
            tables[-1].rows.append(table_row)
    return tables


def _merge_split_numbers(tokens: list[Token], thousands: str) -> list[tuple[Token, str | None]]:
    """Une una cifra partida por un espacio ("359," + "170") y anota la corrección."""
    head = re.compile(r"^\(?\d{1,3}(" + re.escape(thousands) + r"\d{3})*" + re.escape(thousands)
                      + r"$")
    tail = re.compile(r"^\d{3}(" + re.escape(thousands) + r"\d{3})*\)?$")
    merged: list[tuple[Token, str | None]] = []
    for token in tokens:
        if merged and head.fullmatch(merged[-1][0].text) and tail.fullmatch(token.text):
            previous = merged.pop()[0]
            merged.append((Token(previous.text + token.text, previous.x1, token.x2,
                                 min(previous.confidence, token.confidence)),
                           "espacio dentro de la cifra"))
        else:
            merged.append((token, None))
    return merged


def _table_row(row: Row, column_x2: tuple[float, ...], thousands: str) -> TableRow:
    gaps = [b - a for a, b in zip(column_x2, column_x2[1:], strict=False)]
    tolerance = 0.35 * min(gaps) if gaps else 0.1 * column_x2[0]
    label_tokens, amounts, conflict = [], {}, None
    for token, merge_fix in _merge_split_numbers(row.tokens(), thousands):
        amount = parse_amount(token.text, thousands)
        distances = [abs(token.x2 - x2) for x2 in column_x2]
        column = distances.index(min(distances))
        if amount is not None and min(distances) <= tolerance:
            if column in amounts:
                conflict = f"dos importes en la misma columna de la fila {row.text!r}"
                continue
            fixes = amount.fixes + ((merge_fix,) if merge_fix else ())
            amounts[column] = Amount(amount.value, amount.raw, fixes, token.confidence,
                                     dash=amount.dash)
        else:
            label_tokens.append(token.text)
    note = None
    # Referencia a una nota al final del rótulo: "3", "4,5" o "(31)".
    if label_tokens and re.fullmatch(r"\d{1,2}(,\d{1,2})?|\(\d{1,2}\)", label_tokens[-1]):
        note = label_tokens.pop()
    raw_label = " ".join(re.sub(r"\.{2,}", " ", " ".join(label_tokens)).split())
    return TableRow(normalize_label(raw_label), raw_label, note,
                    {} if conflict else dict(sorted(amounts.items())), row, conflict)
