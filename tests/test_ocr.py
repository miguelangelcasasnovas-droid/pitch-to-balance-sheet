"""Lectura de tablas y OCR.

El test de extremo a extremo (imagen -> OCR -> cifra) usa Apple Vision y solo corre en macOS;
en el CI, que es Linux, se salta. El resto no hace OCR y corre en todas partes.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pitch_to_balance_sheet.extract import ocr
from pitch_to_balance_sheet.extract.statements import (
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
    read_document,
)
from pitch_to_balance_sheet.extract.tables import (
    THOUSANDS_EVIDENCE,
    Observation,
    Row,
    Table,
    TableRow,
    group_rows,
    parse_amount,
    read_tables,
)
from pitch_to_balance_sheet.extract.text_layer import measure

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("raw", "thousands", "value", "fixes"),
    [
        ("490,857", ",", 490857, ()),
        ("(428,673)", ",", -428673, ()),
        ("-", ",", 0, ()),
        ("3", ",", 3, ()),
        ("490.857", ",", 490857, ("punto en lugar de separador de miles",)),
        ("(88;608)", ",", -88608, ("punto y coma en lugar de coma de miles",)),
        ("(428,673", ",", -428673, ("paréntesis sin pareja",)),
        ("49O,857", ",", 490857, ("letra leída en lugar de dígito",)),
        ("529.630", ".", 529630, ()),  # formato italiano
        ("(58.146)", ".", -58146, ()),
    ],
)
def test_importes_tal_como_se_leen(raw, thousands, value, fixes):
    amount = parse_amount(raw, thousands)
    assert (amount.value, amount.fixes) == (value, fixes)


@pytest.mark.parametrize("raw", ["Turnover", "2025", "12,34", "(1,23,456)"])
def test_lo_que_no_es_un_importe(raw):
    assert parse_amount(raw) is None


def obs(text, x1, x2, y):
    return Observation(text, 1.0, (x1, y, x2, y + 40))


def test_filas_y_columnas_desde_las_observaciones():
    observations = [
        obs("£'000", 1500, 1610, 100), obs("€'000", 1800, 1910, 102),
        obs("Turnover", 200, 400, 200), obs("3", 1000, 1020, 201),
        obs("1,000", 1500, 1610, 199), obs("900", 1840, 1910, 200),
        obs("Other operating income", 200, 700, 260), obs("500", 1840, 1912, 261),
        obs("Wages", 200, 330, 320), obs("359,", 1760, 1830, 320), obs("170", 1840, 1910, 320),
    ]
    [table] = read_tables(group_rows(observations))
    assert table.header_raw == ("£'000", "€'000")
    turnover, other, wages = table.rows
    assert (turnover.label, turnover.note) == ("turnover", "3")
    assert {c: a.value for c, a in turnover.amounts.items()} == {0: 1000, 1: 900}
    assert other.label == "other operating income"
    assert {c: a.value for c, a in other.amounts.items()} == {1: 500}  # la celda 0, sin leer
    assert wages.amounts[1].value == 359170
    assert wages.amounts[1].fixes == ("espacio dentro de la cifra",)


def test_puntos_de_relleno_fuera_del_rotulo():
    observations = [obs("£'000", 1500, 1610, 100),
                    obs("Revenue ........................ 4", 200, 1100, 200),
                    obs("666,514", 1500, 1610, 200)]
    [table] = read_tables(group_rows(observations))
    [row] = table.rows
    assert (row.label, row.raw_label, row.note) == ("revenue", "Revenue", "4")
    assert row.amounts[0].value == 666514


def test_dos_cifras_en_la_misma_columna_marcan_la_fila_sin_romper_la_tabla():
    observations = [obs("£'000", 1500, 1610, 100), obs("Consideration", 200, 480, 200),
                    obs("66,781", 1400, 1530, 200), obs("92,037", 1480, 1610, 200)]
    [table] = read_tables(group_rows(observations))
    [row] = table.rows
    assert row.amounts == {} and "misma columna" in row.conflict


def blank_cell():
    return Image.new("L", (220, 58), 255)


def test_celda_sin_tinta_es_vacia():
    assert ocr.read_cell(blank_cell(), (0, 0, 220, 58), text_height=51) is None


def test_guion_detectado_aunque_asome_la_fila_de_arriba_o_haya_raya_de_subtotal():
    image = blank_cell()
    draw = ImageDraw.Draw(image)
    draw.rectangle((170, 27, 178, 30), fill=0)  # el guion
    draw.rectangle((60, 0, 175, 2), fill=0)  # resto de la fila de arriba, pegado al borde
    draw.rectangle((0, 49, 203, 51), fill=0)  # raya de subtotal que cruza la celda
    amount = ocr.read_cell(image, (0, 0, 220, 58), text_height=51)
    assert (amount.value, amount.dash) == (0, True)


def test_celda_con_tinta_en_un_pdf_con_texto_es_error_y_no_se_hace_ocr():
    image = blank_cell()
    ImageDraw.Draw(image).rectangle((60, 15, 180, 40), fill=0)
    with pytest.raises(ocr.OcrError, match="no está en el texto del PDF"):
        ocr.read_cell(image, (0, 0, 220, 58), text_height=51, allow_ocr=False)


def test_la_banda_de_una_celda_no_llega_a_la_fila_vecina():
    def table_row(y):
        return TableRow("x", "x", None, {}, Row([obs("x", 0, 10, y)]))

    rows = [table_row(100), table_row(144), table_row(188)]  # centros en 120, 164 y 208
    table = Table(("£'000",), (500.0,), rows)
    _, top, _, bottom = table.cell_box(rows[1], 0, text_height=51)
    # Sin el límite, ±0,55 × 51 daría 136-192 y pisaría los puntos medios con las vecinas.
    assert 142 < top and bottom < 186


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision solo existe en macOS")
def test_imagen_ocr_cifra(tmp_path):
    pytest.importorskip("ocrmac")
    pdf = FIXTURES / "pagina_ocr.pdf"
    assert measure(pdf).classification == "imagen"  # de verdad no tiene capa de texto

    rows = {
        "turnover": r"^turnover$",
        "cost_of_sales": r"^cost of sales$",
        "gross_profit": r"^gross profit$",
        "administrative_expenses": r"^administrative expenses$",
        "other_operating_income": r"^other operating income$",
        "net_result": r"^loss for the financial year$",
    }
    spec = DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(TableSpec("pnl", 1, ("2025", "2024"), rows, sums=(
            Sum("gross_profit", ("turnover", "cost_of_sales")),
            Sum("net_result", ("gross_profit", "administrative_expenses",
                               "other_operating_income")),
        )),),
        figures=(FigureSpec("revenue_total", (("pnl", "turnover"),), "2025"),
                 FigureSpec("net_result", (("pnl", "net_result"),), "2025")),
    )
    result = read_document("principal", spec, pdf, "fixture", tmp_path, reocr=True)

    revenue, net = result.figures
    assert (revenue.value, revenue.page, revenue.label) == (123_456, 1, "Turnover")
    assert net.value == -4_321
    assert all(check.ok for check in result.checks)
    assert len(result.checks) == 4
    assert (tmp_path / "ocr" / "fixture" / "page-001.json").exists()
