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
    SentenceFigureSpec,
    Sum,
    TableSpec,
    read_document,
    sentence_amount,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE, Observation, Row

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
    with pytest.raises(ExtractionError, match="el cuadre que lo contiene no cuadra: net_result "
                                              "= turnover \\+ other_income"):
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

    assert len(SPECS) == 14
    required = ["revenue_total_reported", "revenue_ex_player_trading", "staff_costs",
                "net_result"]
    for club_spec in SPECS.values():
        for document in (club_spec.primary, *club_spec.controls):
            if document.pending:
                continue
            concepts = [f.concept for f in document.figures if f.concept in required]
            assert concepts == required, club_spec.club_id

    def included(concept):
        return {club_id: figure.included_in_staff_costs
                for club_id, club_spec in SPECS.items()
                for figure in (*club_spec.primary.figures, *club_spec.primary.sentences)
                if figure.concept == concept}

    assert included("staff_costs_exceptional") == {"manchester_united": "true",
                                                    "celtic": "dudoso"}
    assert included("staff_severance_disclosed") == {"tottenham": "false", "benfica": "true",
                                                      "juventus": "true", "porto": "true"}
    attributable = {club_id for club_id, club_spec in SPECS.items()
                    if any(f.concept == "net_result_attributable_parent"
                           for f in club_spec.primary.figures)}
    assert attributable == {"borussia_dortmund", "ajax", "porto"}
    assert (SPECS["lazio"].unit, SPECS["lazio"].multiplier) == ("units", 1)
    assert not any(d.pending for s in SPECS.values() for d in (s.primary, *s.controls))
    assert SPECS["borussia_dortmund"].primary.thousands == "."
    assert SPECS["borussia_dortmund"].controls[0].control_kind == "identical"
    assert SPECS["manchester_united"].controls[0].control_kind == "restatement"
    assert SPECS["lazio"].primary.method == "ixbrl"
    assert SPECS["lazio"].primary.periods["2025"] == "2024-07-01/2025-06-30"
    assert SPECS["porto"].primary.tables[0].columns == ("2024", "2025")  # 2024 va antes
    assert set(SPECS["porto"].controls[0].without) == {
        "staff_severance_disclosed", "revenue_matchday", "revenue_commercial",
        "amortisation_player_registrations", "impairment_player_registrations",
        "profit_on_player_disposals", "player_trading_other_income"}


def test_included_in_staff_costs_solo_admite_true_false_o_dudoso():
    with pytest.raises(ValueError, match="included_in_staff_costs"):
        FigureSpec("staff_severance_disclosed", (("t", "r"),), "2025",
                   included_in_staff_costs="sí")


def _sentence_rows(text):
    return [Row([Observation("Salaries and bonuses 222,816", 1.0, (0, 0, 900, 30))]),
            Row([Observation(text, 1.0, (0, 100, 1800, 130))])]


def _sentence(**changes):
    fields = {"concept": "staff_severance_disclosed", "page": 35, "label": "redundancy costs",
              "pattern": r"redundancy costs of (?P<amount>\S+) \(?2024: ?£?86,000\)",
              "column": "2025", "scale": 1000, "included_in_staff_costs": "false"}
    return SentenceFigureSpec(**(fields | changes))


def test_cifra_de_una_frase_en_libras_pasa_a_miles():
    rows = _sentence_rows("redundancy costs of £153,000 (2024: £86,000) were also charged")
    amount, row = sentence_amount(rows, _sentence(), ",")
    assert (amount.value, amount.raw, amount.fixes) == (153, "£153,000", ())
    assert row is rows[1]


def test_si_el_ocr_lee_mal_la_frase_es_error_salvo_con_lectura_en_la_imagen():
    rows = _sentence_rows("payrol costs, redundancy costs of €153,00 2024: 86,000) were also")
    with pytest.raises(ExtractionError, match="leerlo en la imagen"):
        sentence_amount(rows, _sentence(), ",")
    amount, _ = sentence_amount(rows, _sentence(image_reading="£153,000"), ",")
    assert amount.value == 153 and amount.raw == "€153,00"
    assert "leída en la imagen (£153,000) porque el OCR falló" in amount.fixes[0]


def test_la_lectura_en_la_imagen_sobra_si_el_ocr_ya_lee_la_cifra():
    rows = _sentence_rows("redundancy costs of £153,000 (2024: £86,000) were also charged")
    with pytest.raises(ExtractionError, match="sobra image_reading"):
        sentence_amount(rows, _sentence(image_reading="£153,000"), ",")


@pytest.mark.parametrize(
    ("text", "error"),
    [("redundancy costs of £153,500 (2024: £86,000)", "múltiplo exacto"),
     ("redundancy costs of £153,000 (2023: £86,000)", "aparece 0 veces")],
)
def test_frase_que_no_cuadra_con_la_escala_o_que_no_aparece_es_error(text, error):
    with pytest.raises(ExtractionError, match=error):
        sentence_amount(_sentence_rows(text), _sentence(), ",")


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


@pytest.mark.parametrize(("rows", "tolerance"),
                         [(1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (8, 4), (9, 4)])
def test_la_tolerancia_crece_con_las_filas_sumadas(rows, tolerance):
    from pitch_to_balance_sheet.extract.statements import Check

    assert Check("d", 1, "r", "2025", 0, 0, rows=rows).tolerance == tolerance


def test_un_cuadre_que_pasa_con_diferencia_lleva_la_marca_redondeo():
    from pitch_to_balance_sheet.extract.statements import Check

    rounded = Check("d", 154, "total = ocho filas", "2025", 81939, 81937, rows=8)
    assert rounded.ok and rounded.rounding and rounded.note == "redondeo (8 filas)"
    exact = Check("d", 1, "r", "2025", 10, 10, rows=3)
    assert exact.ok and not exact.rounding and exact.note == ""
    assert not Check("d", 1, "r", "2025", 12, 10, rows=3).ok  # 3 filas: tolerancia 1


def _row(y, *words):
    """Una fila de palabras (texto, x1, x2) a la altura y."""
    return Row([Observation(text, 1.0, (x1, y, x2, y + 20)) for text, x1, x2 in words])


def test_cabecera_en_dos_lineas_se_une_si_se_pide():
    from pitch_to_balance_sheet.extract.tables import read_tables

    rows = [_row(0, ("Segm.", 100, 150), ("A", 160, 170), ("Total", 400, 450)),
            _row(30, ("servicos", 300, 350)),
            _row(60, ("Clientes", 0, 80), ("88.231", 120, 170), ("2.132", 310, 350),
                  ("149.540", 390, 450))]
    joined = read_tables(rows, r"^(A|servi\S+|Total)$", ".", join_header_lines=True)
    assert [t.header_raw for t in joined] == [("A", "servicos", "Total")]
    assert {k: a.value for k, a in joined[0].rows[0].amounts.items()} == {
        0: 88231, 1: 2132, 2: 149540}
    apart = read_tables(rows, r"^(A|servi\S+|Total)$", ".")
    assert [t.header_raw for t in apart] == [("A", "Total"), ("servicos",)]


def test_fila_que_va_justo_despues_de_su_ancla():
    from pitch_to_balance_sheet.extract.statements import row_after
    from pitch_to_balance_sheet.extract.tables import read_tables

    rows = [_row(0, ("2025", 400, 450)),
            _row(30, ("Net", 0, 40), ("profit", 45, 90), ("10", 430, 450)),
            _row(60, ("attributable", 0, 90), ("to:", 95, 110)),
            _row(90, ("-", 0, 5), ("Owners", 10, 60), ("of", 65, 75), ("the", 80, 100),
                  ("parent:", 105, 150), ("10", 430, 450)),
            _row(120, ("Comprehensive", 0, 100), ("attributable", 105, 190), ("to:", 195, 210)),
            _row(150, ("-", 0, 5), ("Owners", 10, 60), ("of", 65, 75), ("the", 80, 100),
                  ("parent:", 105, 150), ("12", 430, 450))]
    table = read_tables(rows, r"^2025$")[0]
    row = row_after(table, r"^attributable to$", r"owners of the parent$", "parent", 1)
    assert row.amounts[0].value == 10
    with pytest.raises(ExtractionError, match="aparece 2 veces"):
        row_after(table, r"attributable to$", r"owners of the parent$", "parent", 1)


def test_una_parte_con_menos_se_resta_y_el_bloque_elige_sus_filas():
    from pitch_to_balance_sheet.extract.statements import LoadedTable, _checks, block_rows
    from pitch_to_balance_sheet.extract.tables import read_tables

    rows = [_row(0, ("2025", 400, 450)),
            _row(30, ("Cost", 0, 40)),
            _row(60, ("At", 0, 20), ("1", 25, 30), ("July", 35, 70), ("50", 430, 450)),
            _row(90, ("Amortisation", 0, 90)),
            _row(120, ("At", 0, 20), ("1", 25, 30), ("July", 35, 70), ("20", 430, 450)),
            _row(150, ("Charge", 0, 60), ("7", 440, 450)),
            _row(180, ("Disposals", 0, 70), ("2", 440, 450)),
            _row(210, ("At", 0, 20), ("30", 25, 40), ("June", 45, 80), ("25", 430, 450)),
            _row(240, ("Net", 0, 30), ("book", 35, 70), ("value", 75, 110))]
    table = read_tables(rows, r"^2025$")[0]
    with pytest.raises(ExtractionError, match="aparece 2 veces"):
        block_rows(table, (r"^at 1 july$", r"^at 30 june$"), 1)
    block = block_rows(table, (r"^amortisation$", r"^at 30 june$"), 1)
    assert [row.label for row in block.rows] == ["amortisation", "at 1 july", "charge",
                                                 "disposals", "at 30 june"]
    spec = TableSpec("fund", 1, ("2025",), {}, sums=(
        Sum("closing", ("opening", "charge", "-disposals")),))
    found = {key: block.rows[index] for key, index in
             (("opening", 1), ("charge", 2), ("disposals", 3), ("closing", 4))}
    (check,) = _checks("x", {"fund": LoadedTable(spec, block, found, None)}, ())
    assert (check.relation, check.reported, check.computed) == (
        "closing = opening + charge − disposals", 25, 25)


def test_link_sum_con_signo():
    from pitch_to_balance_sheet.extract.statements import LinkSum, LoadedTable, _checks
    from pitch_to_balance_sheet.extract.tables import read_tables

    rows = [_row(0, ("2025", 400, 450)), _row(30, ("Amortisation", 0, 90), ("(99,868)", 390, 450)),
            _row(60, ("Charge", 0, 60), ("99,502", 400, 450)),
            _row(90, ("Impairment", 0, 80), ("366", 420, 450))]
    table = read_tables(rows, r"^2025$")[0]
    found = dict(zip(("pnl", "charge", "impairment"), table.rows, strict=True))
    loaded = {"t": LoadedTable(TableSpec("t", 1, ("2025",), {}), table, found, None)}
    (check,) = _checks("x", loaded, (LinkSum(("t", "pnl", "2025"), (
        ("t", "charge", "2025"), ("t", "impairment", "2025")), sign=-1),))
    assert check.ok and check.relation == "t.pnl.2025 = -(t.charge.2025 + t.impairment.2025)"


def test_la_cabecera_espaciada_letra_a_letra_se_une():
    from pitch_to_balance_sheet.extract.tables import read_tables

    rows = [_row(0, ("2", 100, 110), ("0", 110, 120), ("2", 120, 130), ("5", 130, 140),
                  ("2", 300, 310), ("0", 310, 320), ("2", 320, 330), ("4", 330, 340)),
            _row(30, ("Revenue", 0, 70), ("10", 120, 140), ("9", 330, 340))]
    (table,) = read_tables(rows, r"^\d{4}$")
    assert table.header_raw == ("2025", "2024")
    assert {k: a.value for k, a in table.rows[0].amounts.items()} == {0: 10, 1: 9}


def test_nil_en_una_frase_es_cero():
    rows = _sentence_rows("capitalised player registrations were impaired by Enil (2024: one)")
    spec = _sentence(concept="impairment_player_registrations",
                     pattern=r"were impaired by \S?(?P<amount>nil) \(2024")
    amount, _ = sentence_amount(rows, spec, ",")
    assert amount.value == 0 and "nil" in amount.fixes[0]


def test_un_concepto_no_puede_ser_hueco_y_cifra(tmp_path):
    figures = FIGURES
    spec_ = DocumentSpec(method="text", tables=spec().tables, figures=figures,
                         unit_evidence=THOUSANDS_EVIDENCE, gaps={"net_result": "no se publica"})
    with pytest.raises(ExtractionError, match="hueco y cifra a la vez"):
        read_document("principal", spec_, TABLE, "fixture", tmp_path)


def test_una_cifra_de_una_frase_se_usa_como_celda(tmp_path):
    from dataclasses import replace

    from pitch_to_balance_sheet.extract.statements import TextCellSpec

    base = spec()
    text = replace(base, text_cells=(
        TextCellSpec("frases", "turnover", 1, "Turnover en el texto",
                     r"^Turnover (?P<amount>[\d,]+) 900$"),),
        links=(Link(("frases", "turnover", "2025"), ("pnl", "turnover", "2025")),),
        figures=(*base.figures, FigureSpec("revenue_other", (
            Part("pnl", "turnover"), Part("frases", "turnover", sign=-1)), "2025")))
    result = read_document("principal", text, TABLE, "fixture", tmp_path)
    link = [check for check in result.checks if check.relation.startswith("frases.")]
    assert [(c.reported, c.computed, c.ok) for c in link] == [(1000, 1000, True)]
    (other,) = [f for f in result.figures if f.concept == "revenue_other"]
    assert other.value == 0 and other.components[1].label == "Turnover en el texto"
