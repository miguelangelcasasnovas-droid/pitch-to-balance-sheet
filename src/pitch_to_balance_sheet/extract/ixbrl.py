"""Lector de iXBRL (Inline XBRL, el formato ESEF), solo con la librería estándar.

Del informe XHTML de un paquete ESEF (un ZIP) lee los hechos numéricos etiquetados
(ix:nonFraction): concepto, contexto (entidad, periodo y dimensiones), unidad, decimals, escala,
signo y el texto tal como se ve. El valor es ese texto transformado según su formato (ixt),
multiplicado por 10^scale y con el signo de sign="-". De cada hecho se guardan también la
página del XHTML y la fila de la tabla donde está, para citarlo.

Del mismo paquete lee el linkbase de cálculo (*_cal.xml): el peso (+1 o -1) de cada partida en
su subtotal, tal como lo declara el emisor. Y las tablas del XHTML, página a página, con el texto
de cada celda: las notas que no están etiquetadas se leen de ahí, citadas por página y fila.

Un formato de número que no se conoce, un hecho sin contexto o sin unidad, o dos hechos del
mismo concepto y contexto con valores distintos son un error: nunca se adivina.
"""

import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

IX = "{http://www.xbrl.org/2013/inlineXBRL}"
XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
XHTML = "{http://www.w3.org/1999/xhtml}"
LINK = "{http://www.xbrl.org/2003/linkbase}"
XLINK = "{http://www.w3.org/1999/xlink}"
# Página del XHTML: el id del bloque de cada página, p. ej. "v1-page141-cflshid_7".
PAGE_ID = re.compile(r"(?:^|[^a-z])page[-_]?(\d+)", re.IGNORECASE)
REPORT_SUFFIXES = (".xhtml", ".html", ".htm")
# Para que la fila guardada lleve prefijos legibles (html:, ix:).
ET.register_namespace("html", XHTML[1:-1])
ET.register_namespace("ix", IX[1:-1])


class IxbrlError(RuntimeError):
    """El paquete o un hecho no se puede leer sin adivinar."""


def concept_key(name: str) -> str:
    """Nombre de concepto para comparar: en NFC, porque un informe puede escribir "à" como "a"
    más el acento combinado (el de Lazio lo hace). La cita conserva el nombre tal cual."""
    return unicodedata.normalize("NFC", name)


@dataclass(frozen=True)
class Context:
    id: str
    entity: str  # identificador de la entidad, p. ej. el LEI
    start: str | None  # periodo de duración: inicio y fin (AAAA-MM-DD)
    end: str | None
    instant: str | None  # o un instante
    dimensions: tuple[tuple[str, str], ...]  # (dimensión, miembro); vacío en el perímetro base

    @property
    def period(self) -> str:
        return self.instant or f"{self.start}/{self.end}"


@dataclass(frozen=True)
class Fact:
    id: str
    concept: str  # tal como lo escribe el informe, p. ej. "ifrs-full:EmployeeBenefitsExpense"
    context: Context
    unit: str  # medidas de la unidad, p. ej. "iso4217:EUR"
    decimals: str
    scale: int
    sign: str  # "-" si el hecho es negativo
    format: str
    raw: str  # el texto que se ve en el informe
    value: Decimal
    page: int | None
    label: str  # primera celda de la fila de la tabla, si el hecho está en una tabla
    row_html: str  # la fila entera, en XHTML, para el recorte


@dataclass(frozen=True)
class XhtmlRow:
    """Una fila de una tabla del XHTML: el texto de cada celda y la fila en XHTML."""

    cells: tuple[str, ...]
    html: str


@dataclass(frozen=True)
class Report:
    name: str  # ruta del informe dentro del ZIP
    facts: tuple[Fact, ...]
    # (subtotal, partida) -> peso, del linkbase de cálculo; conceptos con concept_key.
    calculations: dict[tuple[str, str], Decimal]
    # página -> tablas de esa página, cada una con sus filas
    tables: dict[int, tuple[tuple[XhtmlRow, ...], ...]] = field(default_factory=dict)
    # página -> su texto, con los espacios normalizados (para las cifras que solo están en una
    # frase)
    texts: dict[int, str] = field(default_factory=dict)

    def find(self, concept: str, entity: str, period: str,
             dimensions: tuple[tuple[str, str], ...] = ()) -> Fact:
        """El hecho de un concepto en un periodo y perímetro. Los duplicados tienen que valer
        lo mismo."""
        matches = [f for f in self.facts
                   if concept_key(f.concept) == concept_key(concept) and f.context.entity == entity
                   and f.context.period == period and f.context.dimensions == dimensions]
        if not matches:
            raise IxbrlError(f"no hay ningún hecho {concept} de {entity} en {period}"
                             + (f" con {dimensions}" if dimensions else " sin dimensiones"))
        values = {f.value for f in matches}
        if len(values) > 1:
            raise IxbrlError(f"{concept} en {period} tiene valores distintos: "
                             + ", ".join(f"{f.id}={f.value}" for f in matches))
        return matches[0]


def transform(raw: str, fmt: str | None) -> Decimal:
    """Texto del hecho -> número, según su formato ixt (sin escala ni signo)."""
    name = (fmt or "").rsplit(":", 1)[-1]
    text = re.sub(r"[\s  ]", "", raw)
    if name in ("fixed-zero", "zerodash", "fixedzero"):
        return Decimal(0)
    if name in ("num-dot-decimal", "numdotdecimal", ""):
        number = text.replace(",", "")
    elif name in ("num-comma-decimal", "numcommadecimal"):
        number = text.replace(".", "").replace(",", ".")
    else:
        raise IxbrlError(f"formato ixt no previsto: {fmt!r} (texto {raw!r})")
    if not re.fullmatch(r"\d+(\.\d+)?", number):
        raise IxbrlError(f"{raw!r} no es un número en el formato {fmt!r}")
    try:
        return Decimal(number)
    except InvalidOperation as exc:
        raise IxbrlError(f"{raw!r} no es un número en el formato {fmt!r}") from exc


def _text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _date(period: ET.Element, tag: str) -> str | None:
    node = period.find(XBRLI + tag)
    return node.text.strip() if node is not None and node.text else None


def _contexts(root: ET.Element) -> dict[str, Context]:
    contexts = {}
    for element in root.iter(XBRLI + "context"):
        identifier = element.find(f"{XBRLI}entity/{XBRLI}identifier")
        period = element.find(XBRLI + "period")
        if identifier is None or period is None:
            raise IxbrlError(f"el contexto {element.get('id')} no tiene entidad o periodo")
        dimensions = []
        for container in (element.find(f"{XBRLI}entity/{XBRLI}segment"),
                          element.find(XBRLI + "scenario")):
            if container is None:
                continue
            for member in container:
                if member.tag == XBRLDI + "explicitMember":
                    dimensions.append((member.get("dimension"), (member.text or "").strip()))
                elif member.tag == XBRLDI + "typedMember":
                    dimensions.append((member.get("dimension"), _text(member)))

        contexts[element.get("id")] = Context(
            element.get("id"), identifier.text.strip(), _date(period, "startDate"),
            _date(period, "endDate"), _date(period, "instant"), tuple(sorted(dimensions)))
    return contexts


def _units(root: ET.Element) -> dict[str, str]:
    units = {}
    for element in root.iter(XBRLI + "unit"):
        divide = element.find(XBRLI + "divide")
        if divide is None:
            units[element.get("id")] = " ".join(
                m.text.strip() for m in element.iter(XBRLI + "measure"))
        else:
            numerator = " ".join(m.text.strip() for m in divide.find(
                XBRLI + "unitNumerator").iter(XBRLI + "measure"))
            denominator = " ".join(m.text.strip() for m in divide.find(
                XBRLI + "unitDenominator").iter(XBRLI + "measure"))
            units[element.get("id")] = f"{numerator}/{denominator}"
    return units


def _walk(root: ET.Element):
    """Recorre el XHTML y da cada ix:nonFraction con su página y su fila de tabla."""
    stack = [(root, None, None)]
    while stack:
        element, page, row = stack.pop()
        match = PAGE_ID.search(element.get("id") or "") if element.tag == XHTML + "div" else None
        if match:
            page = int(match.group(1))
        if element.tag == XHTML + "tr":
            row = element
        if element.tag == IX + "nonFraction":
            yield element, page, row
        stack.extend((child, page, row) for child in reversed(element))


def _label(row: ET.Element | None) -> str:
    if row is None:
        return ""
    cells = [cell for cell in row if cell.tag in (XHTML + "td", XHTML + "th")]
    return _text(cells[0]) if cells else ""


def _tables(root: ET.Element) -> dict[int, tuple[tuple[XhtmlRow, ...], ...]]:
    """Las tablas de cada página del XHTML (el bloque más externo con número de página)."""
    pages: dict[int, list[tuple[XhtmlRow, ...]]] = {}
    stack = [root]
    while stack:
        element = stack.pop()
        match = PAGE_ID.search(element.get("id") or "") if element.tag == XHTML + "div" else None
        if not match:
            stack.extend(reversed(element))
            continue
        for table in element.iter(XHTML + "table"):
            rows = tuple(
                XhtmlRow(tuple(_text(cell) for cell in row
                               if cell.tag in (XHTML + "td", XHTML + "th")),
                         ET.tostring(row, encoding="unicode"))
                for row in table.iter(XHTML + "tr"))
            pages.setdefault(int(match.group(1)), []).append(rows)
    return {page: tuple(tables) for page, tables in pages.items()}


def _texts(root: ET.Element) -> dict[int, str]:
    """El texto de cada página del XHTML (el bloque más externo con número de página)."""
    pages: dict[int, list[str]] = {}
    stack = [root]
    while stack:
        element = stack.pop()
        match = PAGE_ID.search(element.get("id") or "") if element.tag == XHTML + "div" else None
        if not match:
            stack.extend(reversed(element))
            continue
        pages.setdefault(int(match.group(1)), []).append(_text(element))
    return {page: " ".join(parts) for page, parts in pages.items()}


def _calculations(package: zipfile.ZipFile) -> dict[tuple[str, str], Decimal]:
    weights: dict[tuple[str, str], Decimal] = {}
    for name in package.namelist():
        if not name.endswith("_cal.xml"):
            continue
        root = ET.fromstring(package.read(name))
        for link in root.iter(LINK + "calculationLink"):
            # El id del elemento en el esquema es "prefijo_Nombre": se pasa a "prefijo:Nombre".
            locators = {loc.get(XLINK + "label"): concept_key(
                loc.get(XLINK + "href").split("#")[-1].replace("_", ":", 1))
                for loc in link.iter(LINK + "loc")}
            for arc in link.iter(LINK + "calculationArc"):
                key = (locators[arc.get(XLINK + "from")], locators[arc.get(XLINK + "to")])
                weight = Decimal(arc.get("weight"))
                if weights.setdefault(key, weight) != weight:
                    raise IxbrlError(f"el linkbase de cálculo da dos pesos a {key}")
    return weights


def read_report(path: Path) -> Report:
    """Hechos numéricos y pesos de cálculo de un paquete ESEF (ZIP)."""
    try:
        package = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise IxbrlError(f"{path.name} no es un ZIP") from exc
    with package:
        reports = [n for n in package.namelist()
                   if "/reports/" in f"/{n}" and n.lower().endswith(REPORT_SUFFIXES)]
        if len(reports) != 1:
            raise IxbrlError(f"{path.name}: se esperaba un informe en reports/ y hay "
                             f"{len(reports)}: {reports}")
        try:
            root = ET.fromstring(package.read(reports[0]))
        except ET.ParseError as exc:
            raise IxbrlError(f"{reports[0]} no es XHTML bien formado: {exc}") from exc
        calculations = _calculations(package)
    contexts, units = _contexts(root), _units(root)
    facts = []
    for element, page, row in _walk(root):
        context = contexts.get(element.get("contextRef"))
        unit = units.get(element.get("unitRef"))
        if context is None or unit is None:
            raise IxbrlError(f"el hecho {element.get('id')} ({element.get('name')}) no tiene "
                             "contexto o unidad")
        raw = _text(element)
        scale = int(element.get("scale", "0"))
        value = transform(raw, element.get("format")) * Decimal(10) ** scale
        sign = element.get("sign", "")
        facts.append(Fact(
            element.get("id", ""), element.get("name"), context, unit,
            element.get("decimals", ""), scale, sign, element.get("format", ""), raw,
            -value if sign == "-" else value, page, _label(row),
            ET.tostring(row, encoding="unicode") if row is not None else ""))
    return Report(reports[0], tuple(facts), calculations, _tables(root), _texts(root))
