"""Motor de extracción sobre una tabla sintética con capa de texto: sin OCR, corre en el CI."""

from pathlib import Path

import pytest

from pitch_to_balance_sheet.extract.statements import (
    DocumentSpec,
    ExtractionError,
    FigureSpec,
    Link,
    Sum,
    TableSpec,
    read_document,
)

TABLE = Path(__file__).parent / "fixtures" / "tabla_texto.pdf"
ROWS = {
    "turnover": r"^turnover$",
    "cost_of_sales": r"^cost of sales$",
    "gross_profit": r"^gross profit$",
    "other_income": r"^other income$",
    "net_result": r"^profit for the year$",
}
GOOD_SUMS = (
    Sum("gross_profit", ("turnover", "cost_of_sales")),
    Sum("net_result", ("gross_profit", "other_income")),
)
FIGURES = (
    FigureSpec("revenue_total", (("pnl", "turnover"),), "2025"),
    FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
)


def spec(sums=GOOD_SUMS, figures=FIGURES, links=()):
    return DocumentSpec(method="text", unit_evidence=r"£.000", links=links, figures=figures,
                        tables=(TableSpec("pnl", 1, ("2025", "2024"), ROWS, sums=sums),))


def test_cifras_con_pagina_fila_y_cuadres(tmp_path):
    result = read_document("principal", spec(), TABLE, "fixture", tmp_path)
    revenue, net = result.figures
    assert (revenue.value, revenue.page, revenue.label, revenue.column) == (
        1000, 1, "Turnover", "2025")
    assert net.value == 600
    assert revenue.ocr_note == "texto del PDF, sin OCR: sin corrección"
    assert [check.ok for check in result.checks] == [True] * 4
    assert (tmp_path / "text" / "fixture" / "page-001.png").exists()


def test_un_cuadre_que_no_cuadra_se_marca(tmp_path):
    wrong = (Sum("gross_profit", ("turnover",)), GOOD_SUMS[1])
    result = read_document("principal", spec(sums=wrong), TABLE, "fixture", tmp_path)
    gross_2025, gross_2024, net_2025, net_2024 = result.checks
    assert not gross_2025.ok and gross_2025.difference == -400  # 600 frente a 1.000
    assert not gross_2024.ok
    assert net_2025.ok and net_2024.ok


def test_un_guion_que_solo_esta_en_un_cuadre_que_falla_es_error(tmp_path):
    wrong = (Sum("net_result", ("turnover", "other_income")),)
    with pytest.raises(ExtractionError, match="ningún cuadre lo respalda"):
        read_document("principal", spec(sums=wrong), TABLE, "fixture", tmp_path)


def test_un_guion_como_cero_sin_cuadre_que_lo_respalde_es_error(tmp_path):
    figures = FIGURES + (FigureSpec("other", (("pnl", "other_income"),), "2025"),)
    only_gross = (Sum("gross_profit", ("turnover", "cost_of_sales")),)
    with pytest.raises(ExtractionError, match="ningún cuadre lo respalda"):
        read_document("principal", spec(sums=only_gross, figures=figures), TABLE, "fixture",
                      tmp_path)


def test_el_mismo_guion_vale_si_su_cuadre_cuadra(tmp_path):
    figures = FIGURES + (FigureSpec("other", (("pnl", "other_income"),), "2025"),)
    result = read_document("principal", spec(figures=figures), TABLE, "fixture", tmp_path)
    assert result.figures[-1].value == 0
    assert result.figures[-1].ocr_note == "texto del PDF, sin OCR: guion→cero"


def test_cifra_suma_de_varias_filas_y_enlace_con_signo(tmp_path):
    figures = (FigureSpec("two_rows", (("pnl", "turnover"), ("pnl", "cost_of_sales")), "2025"),)
    links = (Link(("pnl", "gross_profit", "2025"), ("pnl", "net_result", "2025")),
             Link(("pnl", "cost_of_sales", "2024"), ("pnl", "cost_of_sales", "2024"), sign=-1))
    result = read_document("principal", spec(figures=figures, links=links), TABLE, "fixture",
                           tmp_path)
    assert result.figures[0].value == 600
    assert result.figures[0].label == "Turnover + Cost of sales"
    same, opposite = result.checks[-2:]
    assert same.ok  # 600 y 600
    assert not opposite.ok  # -300 frente a 300


def test_sin_la_unidad_en_la_pagina_es_error(tmp_path):
    no_unit = DocumentSpec(method="text", unit_evidence=r"migliaia di euro", figures=FIGURES,
                           tables=(TableSpec("pnl", 1, ("2025", "2024"), ROWS),))
    with pytest.raises(ExtractionError, match="no se puede confirmar la unidad"):
        read_document("principal", no_unit, TABLE, "fixture", tmp_path)


def test_fila_que_falta_es_error(tmp_path):
    rows = ROWS | {"tax": r"^tax$"}
    missing = DocumentSpec(method="text", unit_evidence=r"£.000", figures=FIGURES,
                           tables=(TableSpec("pnl", 1, ("2025", "2024"), rows),))
    with pytest.raises(ExtractionError, match="la fila tax"):
        read_document("principal", missing, TABLE, "fixture", tmp_path)


def test_las_especificaciones_de_los_ocho_clubes_se_cargan():
    from pitch_to_balance_sheet.extract.clubs import SPECS

    assert sorted(SPECS) == ["arsenal", "celtic", "chelsea", "juventus", "liverpool",
                             "manchester_city", "newcastle", "tottenham"]
    for club_spec in SPECS.values():
        concepts = [f.concept for f in club_spec.primary.figures]
        assert concepts == ["revenue_total", "staff_costs", "net_result"], club_spec.club_id
