"""Chelsea FC Holdings Limited, cuentas 2024/25 de Companies House: piloto de extracción por OCR.

Solo tres cifras: ingresos totales, gastos de personal y resultado neto. Páginas localizadas a mano
mirando la página renderizada (config/sources.yaml):
- pág. 17, Group profit and loss account: cuatro columnas en £'000 (operaciones sin amortización
  ni traspasos de jugadores 2025, amortización y traspasos de jugadores 2025, total 2025 y
  total 2024);
- pág. 34, nota 8, Employees: remuneración agregada, 2025 y 2024 en £'000. En la misma página, la
  nota 9 (remuneración de los consejeros) tiene otro subtotal, que también se comprueba.

Las cuentas están en libras: lo dicen las cabeceras "£'000" y los importes en £ del texto de la
pág. 17, comprobado en la página renderizada. El OCR lee a veces "€'000", así que la moneda no
se toma del OCR: se exige que al menos una cabecera de unidad de cada página diga "£".
"""

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pitch_to_balance_sheet.extract import ocr

CURRENCY = "GBP"
UNIT = "thousands"
MULTIPLIER = 1000
TOLERANCE = 1  # en miles de libras, por redondeo

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025", "total_2024")
PNL_ROWS = {
    "turnover": r"^turnover$",
    "cost_of_sales": r"^cost of sales$",
    "gross_profit": r"^gross profit$",
    "administrative_expenses": r"^administrative expenses$",
    "other_operating_income": r"^other operating income$",
    "operating_loss": r"^operating loss$",
    "interest_receivable": r"^interest receivable",
    "interest_payable": r"^interest payable",
    "profit_disposal_players": r"^profit on disposal of player registrations$",
    "profit_disposal_investments": r"^profit on disposal of fixed asset investments$",
    "disposal_fixed_assets": r"^\(loss\)/profit on disposal of fixed assets$",
    "fair_value_investment_properties": r"^fair value loss on investment properties$",
    # Sic: el PDF rotula "after taxation" la fila que va antes del impuesto.
    "result_before_tax": r"^\(loss\)/profit after taxation$",
    "tax": r"^tax on \(loss\)/profit$",
    "net_result": r"^\(loss\)/profit for the financial year$",
}
PNL_SUMS = [
    ("gross_profit", ["turnover", "cost_of_sales"]),
    ("operating_loss", ["gross_profit", "administrative_expenses", "other_operating_income"]),
    ("result_before_tax", ["operating_loss", "interest_receivable", "interest_payable",
                           "profit_disposal_players", "profit_disposal_investments",
                           "disposal_fixed_assets", "fair_value_investment_properties"]),
    ("net_result", ["result_before_tax", "tax"]),
]
NOTE_COLUMNS = ("2025", "2024")
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "pension_costs": r"^pension costs$",
}
DIRECTORS_ROWS = {
    "directors_remuneration": r"^remuneration for qualifying services$",
    "directors_pension": r"^company pension contributions",
}


class ExtractionError(RuntimeError):
    """Falta una fila, una celda o un subtotal no cuadra."""


@dataclass(frozen=True)
class Figure:
    concept: str
    page: int
    label_original: str
    column: str
    amount: ocr.Amount
    row: ocr.Row


@dataclass(frozen=True)
class Check:
    page: int
    relation: str
    column: str
    reported: int
    computed: int

    @property
    def difference(self) -> int:
        return self.reported - self.computed

    @property
    def ok(self) -> bool:
        return abs(self.difference) <= TOLERANCE


@dataclass
class PageTables:
    page: int
    tables: list[ocr.Table]
    image_path: Path


def read_page(ocr_folder: Path, page: int, columns_per_table: int) -> PageTables:
    observations, image_path = ocr.load_page(ocr_folder, page)
    tables = ocr.read_tables(ocr.group_rows(observations))
    tables = [t for t in tables if len(t.column_x2) == columns_per_table]
    if not tables:
        raise ExtractionError(f"pág. {page}: no hay ninguna tabla de {columns_per_table} columnas")
    units = [unit for table in tables for unit in table.unit_raw]
    if not any(unit.startswith("£") for unit in units):
        raise ExtractionError(f"pág. {page}: ninguna cabecera de unidad dice £ ({units})")
    height = ocr.text_height(observations)
    with Image.open(image_path) as image:
        for table in tables:
            ocr.fill_missing_cells(table, image, height)
    return PageTables(page, tables, image_path)


def find_rows(table: ocr.Table, patterns: dict[str, str], page: int) -> dict[str, ocr.TableRow]:
    found = {}
    for key, pattern in patterns.items():
        matches = [r for r in table.rows if re.search(pattern, r.label)]
        if len(matches) != 1:
            raise ExtractionError(
                f"pág. {page}: la fila {key} ({pattern}) aparece {len(matches)} veces"
            )
        found[key] = matches[0]
    return found


def total_after(table: ocr.Table, last: ocr.TableRow, page: int) -> ocr.TableRow:
    """La fila de total sin rótulo que va justo después de la última partida."""
    index = table.rows.index(last) + 1
    if index >= len(table.rows) or table.rows[index].label or not table.rows[index].amounts:
        raise ExtractionError(f"pág. {page}: no hay fila de total después de {last.raw_label!r}")
    return table.rows[index]


def value(row: ocr.TableRow, column: int, key: str, page: int) -> int:
    if column not in row.amounts:
        raise ExtractionError(f"pág. {page}: la fila {key} no tiene importe en la columna {column}")
    return row.amounts[column].value


def check_sum(page, rows, total_key, component_keys, columns) -> list[Check]:
    checks = []
    for index, column in enumerate(columns):
        computed = sum(value(rows[key], index, key, page) for key in component_keys)
        checks.append(Check(page, f"{total_key} = " + " + ".join(component_keys), column,
                            value(rows[total_key], index, total_key, page), computed))
    return checks


def extract(ocr_folder: Path) -> tuple[list[Figure], list[Check], list[PageTables]]:
    pnl_page = read_page(ocr_folder, 17, len(PNL_COLUMNS))
    if len(pnl_page.tables) != 1:
        raise ExtractionError(f"pág. 17: se esperaba una tabla y hay {len(pnl_page.tables)}")
    pnl = find_rows(pnl_page.tables[0], PNL_ROWS, 17)
    checks = []
    for total_key, component_keys in PNL_SUMS:
        checks += check_sum(17, pnl, total_key, component_keys, PNL_COLUMNS)
    for key, row in pnl.items():  # operaciones + jugadores = total 2025, fila a fila
        checks.append(Check(17, f"{key}: total_2025 = operations_2025 + players_2025",
                            "total_2025", value(row, 2, key, 17),
                            value(row, 0, key, 17) + value(row, 1, key, 17)))

    note_page = read_page(ocr_folder, 34, len(NOTE_COLUMNS))
    staff_table = next((t for t in note_page.tables
                        if any(r.label == "wages and salaries" for r in t.rows)), None)
    directors_table = next((t for t in note_page.tables
                            if any(r.label.startswith("company pension") for r in t.rows)), None)
    if staff_table is None or directors_table is None:
        raise ExtractionError("pág. 34: no se encuentran las tablas de personal y de consejeros")
    staff = find_rows(staff_table, STAFF_ROWS, 34)
    staff["staff_costs_total"] = total_after(staff_table, staff["pension_costs"], 34)
    checks += check_sum(34, staff, "staff_costs_total", list(STAFF_ROWS), NOTE_COLUMNS)
    directors = find_rows(directors_table, DIRECTORS_ROWS, 34)
    directors["directors_total"] = total_after(directors_table, directors["directors_pension"], 34)
    checks += check_sum(34, directors, "directors_total", list(DIRECTORS_ROWS), NOTE_COLUMNS)

    def figure(concept, page, row, column_index, columns):
        return Figure(concept, page, row.raw_label or "(total sin rótulo)", columns[column_index],
                      row.amounts[column_index], row.row)

    figures = [
        figure("revenue_total", 17, pnl["turnover"], 2, PNL_COLUMNS),
        figure("staff_costs", 34, staff["staff_costs_total"], 0, NOTE_COLUMNS),
        figure("net_result", 17, pnl["net_result"], 2, PNL_COLUMNS),
    ]
    return figures, checks, [pnl_page, note_page]
