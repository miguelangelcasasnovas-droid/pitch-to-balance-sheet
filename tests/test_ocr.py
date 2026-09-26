"""OCR y lectura de tablas.

El test de extremo a extremo (imagen -> OCR -> cifra) usa Apple Vision y solo corre en macOS;
en el CI, que es Linux, se salta. El resto no hace OCR y corre en todas partes.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pitch_to_balance_sheet.extract import ocr
from pitch_to_balance_sheet.extract.chelsea import Check, ExtractionError, check_sum, find_rows
from pitch_to_balance_sheet.extract.text_layer import measure

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("raw", "value", "fixes"),
    [
        ("490,857", 490857, ()),
        ("(428,673)", -428673, ()),
        ("-", 0, ()),
        ("3", 3, ()),
        ("490.857", 490857, ("punto en lugar de coma de miles",)),
        ("(428,673", -428673, ("paréntesis sin pareja",)),
        ("49O,857", 490857, ("letra leída en lugar de dígito",)),
    ],
)
def test_importes_tal_como_salen_del_ocr(raw, value, fixes):
    amount = ocr.parse_amount(raw)
    assert (amount.value, amount.fixes) == (value, fixes)


@pytest.mark.parametrize("raw", ["Turnover", "2025", "12,34", "(1,23,456)"])
def test_lo_que_no_es_un_importe(raw):
    assert ocr.parse_amount(raw) is None


def obs(text, x1, x2, y):
    return ocr.Observation(text, 1.0, (x1, y, x2, y + 40))


def test_filas_y_columnas_desde_las_observaciones():
    observations = [
        obs("£'000", 1500, 1610, 100), obs("€'000", 1800, 1910, 102),
        obs("Turnover", 200, 400, 200), obs("3", 1000, 1020, 201),
        obs("1,000", 1500, 1610, 199), obs("900", 1840, 1910, 200),
        obs("Other operating income", 200, 700, 260), obs("500", 1840, 1912, 261),
    ]
    [table] = ocr.read_tables(ocr.group_rows(observations))
    assert table.unit_raw == ("£'000", "€'000")
    turnover, other = table.rows
    assert (turnover.label, turnover.note) == ("turnover", "3")
    assert {c: a.value for c, a in turnover.amounts.items()} == {0: 1000, 1: 900}
    assert other.label == "other operating income"
    assert {c: a.value for c, a in other.amounts.items()} == {1: 500}  # la celda 0, sin leer


def blank_cell():
    return Image.new("L", (220, 58), 255)


def test_celda_sin_tinta_es_vacia():
    assert ocr.read_cell(blank_cell(), (0, 0, 220, 58), text_height=51) is None


def test_guion_detectado_en_la_imagen_aunque_asome_la_fila_de_arriba():
    image = blank_cell()
    draw = ImageDraw.Draw(image)
    draw.rectangle((170, 33, 180, 36), fill=0)  # el guion
    draw.rectangle((60, 0, 175, 2), fill=0)  # resto de la fila de arriba, pegado al borde
    amount = ocr.read_cell(image, (0, 0, 220, 58), text_height=51)
    assert amount.value == 0
    assert amount.fixes == ("guion que el OCR no leyó, detectado en la imagen",)


def table_row(label, *values):
    return ocr.TableRow(label, label, None,
                        {i: ocr.Amount(v, str(v)) for i, v in enumerate(values)}, ocr.Row())


def test_un_subtotal_que_no_cuadra_se_detecta():
    rows = {"a": table_row("a", 100, 10), "b": table_row("b", -40, 5),
            "total": table_row("total", 60, 20)}
    first, second = check_sum(17, rows, "total", ["a", "b"], ("2025", "2024"))
    assert first.ok and first.difference == 0
    assert not second.ok and second.difference == 5
    assert Check(17, "x", "2025", 10, 9).ok  # ±1 de redondeo
    assert not Check(17, "x", "2025", 10, 8).ok


def test_fila_que_falta_es_error():
    table = ocr.Table(("£'000",), (100.0,), [table_row("turnover", 1)])
    with pytest.raises(ExtractionError, match="aparece 0 veces"):
        find_rows(table, {"net_result": r"^profit for the financial year$"}, 17)


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision solo existe en macOS")
def test_imagen_ocr_cifra():
    pytest.importorskip("ocrmac")
    pdf = FIXTURES / "pagina_ocr.pdf"
    assert measure(pdf).classification == "imagen"  # de verdad no tiene capa de texto

    image = ocr.render_page(pdf, 1)
    observations = ocr.recognize(image)
    [table] = ocr.read_tables(ocr.group_rows(observations))
    ocr.fill_missing_cells(table, image, ocr.text_height(observations))
    rows = find_rows(table, {
        "turnover": r"^turnover$",
        "cost_of_sales": r"^cost of sales$",
        "gross_profit": r"^gross profit$",
        "administrative_expenses": r"^administrative expenses$",
        "other_operating_income": r"^other operating income$",
        "net_result": r"^loss for the financial year$",
    }, 1)

    assert rows["turnover"].amounts[0].value == 123_456
    assert rows["turnover"].note == "3"
    assert rows["net_result"].amounts[0].value == -4_321
    assert rows["other_operating_income"].amounts[0].value == 0  # el guion
    checks = (check_sum(1, rows, "gross_profit", ["turnover", "cost_of_sales"], ("2025", "2024"))
              + check_sum(1, rows, "net_result", ["gross_profit", "administrative_expenses",
                                                  "other_operating_income"], ("2025", "2024")))
    assert all(check.ok for check in checks)
