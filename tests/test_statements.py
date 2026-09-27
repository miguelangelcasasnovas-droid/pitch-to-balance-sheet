"""Motor de extracción sobre una tabla sintética con capa de texto: sin Vision, corre en el CI.

Para probar el camino del OCR sin Vision se fabrica un "OCR guardado" con el texto del PDF y se
sustituye ocr.recognize por un espía que cuenta las llamadas.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from pitch_to_balance_sheet.extract import ocr, pdf_text
from pitch_to_balance_sheet.extract.statements import (
    DocumentSpec,
    ExtractionError,
    FigureSpec,
    Link,
    Part,
    Sum,
    TableSpec,
    read_document,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE, Observation

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


def spec(sums=GOOD_SUMS, figures=FIGURES, links=(), method="text"):
    return DocumentSpec(method=method, unit_evidence=THOUSANDS_EVIDENCE, links=links,
                        figures=figures,
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


def test_cifra_derivada_con_una_parte_restada_de_otra_columna(tmp_path):
    figures = (FigureSpec("revenue_ex", (Part("pnl", "turnover"),
                                         Part("pnl", "cost_of_sales", "2024", sign=-1)), "2025"),
               FigureSpec("revenue", (("pnl", "turnover"),), "2025"))
    derived, plain = read_document("principal", spec(figures=figures), TABLE, "fixture",
                                   tmp_path).figures
    assert derived.value == 1000 - (-300)
    assert derived.is_derived and not plain.is_derived
    assert derived.sources == ("+ pág. 1 'Turnover' [2025] 1,000 ; "
                               "− pág. 1 'Cost of sales' [2024] -300")


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


def test_filas_por_orden_con_un_numero_de_filas_distinto_es_error(tmp_path):
    def by_order(keys):
        return DocumentSpec(method="text", unit_evidence=THOUSANDS_EVIDENCE, figures=FIGURES,
                            tables=(TableSpec("pnl", 1, ("2025", "2024"), {}, sums=GOOD_SUMS,
                                              rows_by_order=keys,
                                              anchors={"turnover": r"^turnover$"}),))

    result = read_document("principal", by_order(tuple(ROWS)), TABLE, "fixture", tmp_path)
    assert all(check.ok for check in result.checks)
    with pytest.raises(ExtractionError, match="se esperaban 4 filas con cifras y hay 5"):
        read_document("principal", by_order(tuple(ROWS)[:4]), TABLE, "fixture", tmp_path)


def saved_ocr(tmp_path, drop=()) -> list[Observation]:
    """Guarda como "OCR" el texto del PDF sintético, sin pasar Vision."""
    observations = [o for o in pdf_text.page_observations(TABLE, 1) if o.text not in drop]
    paths = ocr.page_paths(tmp_path / "ocr" / "fixture", 1)
    paths["png"].parent.mkdir(parents=True)
    ocr.render_page(TABLE, 1).save(paths["png"])
    paths["json"].write_text(json.dumps({"observations": [asdict(o) for o in observations]}),
                             encoding="utf-8")
    return observations


def test_sin_reocr_se_lee_el_ocr_guardado_y_no_se_llama_a_vision(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ocr, "recognize", lambda image: calls.append(image) or [])
    saved_ocr(tmp_path)
    result = read_document("principal", spec(method="ocr"), TABLE, "fixture", tmp_path)
    assert calls == []
    assert [f.value for f in result.figures] == [1000, 600]


def test_sin_reocr_y_sin_ocr_guardado_es_error_y_no_se_llama_a_vision(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ocr, "recognize", lambda image: calls.append(image) or [])
    with pytest.raises(ExtractionError, match="ejecuta con --reocr"):
        read_document("principal", spec(method="ocr"), TABLE, "fixture", tmp_path)
    assert calls == []


def test_la_segunda_lectura_de_una_celda_solo_pasa_vision_con_reocr(tmp_path, monkeypatch):
    page = saved_ocr(tmp_path, drop={"900"})  # el "OCR" se salta el 900 de 2024
    calls = []

    def vision(image):
        calls.append(image.size)
        if image.width > 1000:  # la página entera
            return page
        return [Observation("900", 0.9, (0, 0, 60, 30))]  # la celda

    monkeypatch.setattr(ocr, "recognize", vision)
    with pytest.raises(ExtractionError, match="segunda lectura guardada.*--reocr"):
        read_document("principal", spec(method="ocr"), TABLE, "fixture", tmp_path)
    assert calls == []

    result = read_document("principal", spec(method="ocr"), TABLE, "fixture", tmp_path,
                           reocr=True)
    assert len(calls) == 2  # la página y la celda
    assert all(check.ok for check in result.checks)

    calls.clear()
    result = read_document("principal", spec(method="ocr"), TABLE, "fixture", tmp_path)
    assert calls == []  # la celda sale de page-001-cells.json
    turnover_2024 = [c for c in result.checks if c.column == "2024"][0]
    assert turnover_2024.ok


def test_las_especificaciones_de_los_clubes_se_cargan():
    from pitch_to_balance_sheet.extract.clubs import SPECS

    assert len(SPECS) == 12
    required = ["revenue_total_reported", "revenue_ex_player_trading", "staff_costs",
                "net_result"]
    for club_spec in SPECS.values():
        for document in (club_spec.primary, *club_spec.controls):
            if document.pending:
                continue
            concepts = [f.concept for f in document.figures if f.concept in required]
            assert concepts == required, club_spec.club_id
    exceptional = {club_id for club_id, club_spec in SPECS.items()
                   if any(f.concept == "staff_costs_exceptional"
                          for f in club_spec.primary.figures)}
    assert exceptional == {"manchester_united", "celtic"}
    assert SPECS["borussia_dortmund"].primary.pending
    assert SPECS["manchester_united"].controls[0].control_kind == "restatement"


def test_una_especificacion_pendiente_es_error_con_su_motivo(tmp_path):
    pending = DocumentSpec(method="text", tables=(), figures=(), unit_evidence="",
                           pending="falta el PDF alemán")
    with pytest.raises(ExtractionError, match="falta el PDF alemán"):
        read_document("principal", pending, TABLE, "fixture", tmp_path)


@pytest.mark.parametrize(
    ("primary", "control", "restated"),
    [(1000, 1000, False), (1000, 1010, False), (1000, 1011, True), (-500, -490, True),
     (0, 0, False)],
)
def test_reexpresion_si_la_cifra_del_ano_siguiente_difiere_mas_de_un_1_por_ciento(
        primary, control, restated):
    from pitch_to_balance_sheet.extract.run import Restatement

    assert Restatement("control", "x", 1, primary, control).restated is restated
