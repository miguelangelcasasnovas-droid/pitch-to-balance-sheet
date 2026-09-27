"""Reparto de ingresos (fase 3a): line_items.yaml, huecos, cifras y validación con pandera."""

import pandas as pd
import pytest

from pitch_to_balance_sheet.extract import mix, run
from pitch_to_balance_sheet.extract.clubs import SPECS
from pitch_to_balance_sheet.extract.statements import IxbrlDocumentSpec, LinkSum

YAML = """
"2024/25":
  ejemplo:
    source: nota 3
    column: "2025"
    total: revenue.total
    items:
      gate: {cell: revenue.gate, label: Gate, concept: revenue_matchday, reason: Taquilla.}
      tv: {cell: revenue.tv, label: TV, concept: revenue_broadcasting, reason: Televisión.}
      retail:
        cell: revenue.retail
        label: Retail
        concept: null
        candidates: [revenue_commercial, revenue_other]
        reason: Retail suelto.
      loans: {cell: revenue.loans, label: Loans, concept: player_trading, reason: Cesiones.}
"""


def _load(tmp_path, text=YAML):
    path = tmp_path / "line_items.yaml"
    path.write_text(text, encoding="utf-8")
    return mix.load("2024/25", path)["ejemplo"]


def test_una_dudosa_deja_sin_cifra_a_sus_candidatos(tmp_path):
    club = _load(tmp_path)
    gaps = club.gaps()
    assert set(gaps) == {"revenue_commercial", "revenue_other"}
    assert "la partida dudosa «Retail» puede ir a revenue_commercial o revenue_other" in (
        gaps["revenue_commercial"])
    figures = {figure.concept: figure for figure in club.figures("2025")}
    assert set(figures) == {"revenue_matchday", "revenue_broadcasting", mix.UNASSIGNED}
    assert [p.row for p in figures[mix.UNASSIGNED].resolved()] == ["retail"]
    assert club.lines == 3  # las cesiones no suman revenue_ex_player_trading
    assert club.check() == LinkSum(("revenue", "total", "2025"), tuple(
        ("revenue", key, "2025") for key in ("gate", "tv", "retail", "loans")))


def test_un_concepto_sin_partidas_es_hueco_con_motivo(tmp_path):
    club = _load(tmp_path, YAML.replace("concept: null", "concept: revenue_commercial")
                 .replace("candidates: [revenue_commercial, revenue_other]", ""))
    assert set(club.gaps()) == {"revenue_other"}
    assert "no tiene una partida de este tipo" in club.gaps()["revenue_other"]


@pytest.mark.parametrize(("old", "new", "error"), [
    ("candidates: [revenue_commercial, revenue_other]", "candidates: [revenue_other]",
     "dos o más candidatos"),
    ("concept: revenue_matchday", "concept: revenue_stadium", "no previsto"),
    ("reason: Televisión.", "reason: ''", "falta el motivo"),
])
def test_el_mapeo_mal_escrito_es_error(tmp_path, old, new, error):
    with pytest.raises(ValueError, match=error):
        _load(tmp_path, YAML.replace(old, new))


def _cells(document) -> set[tuple[str, str]]:
    if isinstance(document, IxbrlDocumentSpec):
        return {("ixbrl", key) for key in document.concepts}
    return {(table.name, key) for table in document.tables
            for key in (*table.rows, *table.totals_after, *table.rows_by_order)}


def test_cada_club_tiene_sus_partidas_y_todas_existen_en_su_especificacion():
    clubs = mix.load()
    assert set(clubs) == set(SPECS)
    for club_id, club in clubs.items():
        document = SPECS[club_id].primary
        cells = _cells(document)
        for item in club.items:
            assert (item.table, item.row) in cells, (club_id, item.key)
        assert club.total[:2] in cells, club_id
        if isinstance(document, IxbrlDocumentSpec):
            # La completitud la da el cálculo del total en el iXBRL: las mismas partidas.
            (calc,) = [c for c in document.calcs if c.total == club.total[1]]
            assert {key for key, _ in calc.parts} == {item.row for item in club.items}
        else:  # el cuadre de que las partidas suman el total va en la especificación
            assert club.check() in document.links, club_id


def test_una_fila_de_ingresos_sin_partida_rompe_el_cuadre():
    """Si se quita una partida del mapeo, el total ya no es la suma de las demás: el cuadre que
    va en la especificación falla (aquí se comprueba sobre las celdas, sin leer el PDF)."""
    club = mix.load()["chelsea"]
    fewer = mix.ClubMix(club.club_id, club.source, club.total, club.items[:-1])
    assert fewer.check() != club.check()
    assert len(fewer.check().parts) == len(club.items) - 1


def _frame(**changes) -> pd.DataFrame:
    row = {"club_id": "x", "revenue_ex_player_trading": 1000.0, "revenue_matchday": 300.0,
           "revenue_broadcasting": 400.0, "revenue_commercial": 200.0, "revenue_other": None,
           "unassigned": 100.0, "lines": 5} | changes
    return pd.DataFrame([row]).astype({"lines": int, "unassigned": float,
                                       **{c: float for c in mix.MIX}})


def test_pandera_valida_el_reparto_con_la_tolerancia_de_redondeo():
    assert run.validate_mix(_frame()) == []
    assert run.validate_mix(_frame(unassigned=102.0)) == []  # 5 partidas: tolerancia 2
    problems = run.validate_mix(_frame(unassigned=103.0))
    assert problems and "diferencia 3, tolerancia 2" in problems[0]


def test_pandera_sin_clubes_no_valida_nada():
    assert run.validate_mix(_frame().iloc[0:0]) == []
