"""Comparación con los controles en extract_club, con documentos simulados: sin archivos."""

import pytest

from pitch_to_balance_sheet.extract import run
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Component,
    DocumentResult,
    DocumentSpec,
    Figure,
)
from pitch_to_balance_sheet.extract.tables import Amount
from pitch_to_balance_sheet.sources.config import Source


def _figure(concept: str, value: int) -> Figure:
    component = Component(1, concept, "2025", 1, Amount(value, f"{value:,}"), None, None)
    return Figure(concept, "2025", value, (component,), "text", "")


def _extract(monkeypatch, primary: list[Figure], control: list[Figure], without=None):
    documents = {None: primary, 0: control}
    monkeypatch.setattr(run, "document_file", lambda season, club_id, index: (
        Source("url", "https://ejemplo.invalid/x.pdf", "web/x.pdf"), "web/x.pdf", "sha"))
    monkeypatch.setattr(run, "read_document", lambda name, spec, *args: DocumentResult(
        name, documents[spec.control_index], [], [], {}))
    monkeypatch.setattr(run, "crop_figure", lambda figure, path: None)
    empty = {"method": "text", "tables": (), "figures": (), "unit_evidence": ""}
    club = ClubSpec("x", "EUR", "thousands", 1000, "", DocumentSpec(**empty),
                    (DocumentSpec(**empty, control_index=0, without=without or {}),))
    return run.extract_club("2024/25", club)


def test_lo_que_el_control_no_trae_queda_sin_control_anotado(monkeypatch):
    result = _extract(
        monkeypatch,
        [_figure("revenue_total_reported", 149541), _figure("staff_severance_disclosed", 3005)],
        [_figure("revenue_total_reported", 149540)],
        without={"staff_severance_disclosed": "el comunicado no desglosa el personal"})
    assert result.error is None
    assert result.controls == [
        "control: web del club: cifras idénticas salvo redondeo en revenue_total_reported "
        "(149,541 frente a 149,540); sin control: staff_severance_disclosed (el comunicado no "
        "desglosa el personal)"]


def test_si_el_control_no_trae_una_cifra_sin_motivo_es_error(monkeypatch):
    result = _extract(monkeypatch, [_figure("staff_costs", 1)], [])
    assert result.error == "el control: web del club no tiene staff_costs"


def test_without_no_puede_esconder_una_cifra_que_el_control_si_trae(monkeypatch):
    result = _extract(monkeypatch, [_figure("staff_costs", 1)], [_figure("staff_costs", 1)],
                      without={"staff_costs": "motivo viejo"})
    assert "sí trae staff_costs" in result.error


@pytest.mark.parametrize(("value", "multiplier", "full"), [(81939, 1000, 81939000)])
def test_la_cifra_completa_es_entera(value, multiplier, full):
    from decimal import Decimal

    assert run._full(value, multiplier) == full
    assert run._full(Decimal("146041.028"), 1000) == 146041028
    with pytest.raises(ValueError, match="no es un entero"):
        run._full(Decimal("0.0005"), 1000)


def test_las_cifras_en_unidades_se_muestran_en_miles_redondeados():
    from decimal import Decimal

    assert run._value(_figure("revenue_total_reported", 146041028), "units") == "146,041"
    assert run._value(_figure("net_result", -17164480), "units") == "(17,164)"
    assert run._value(_figure("x", 1500), "units") == "2"  # la mitad, hacia arriba
    assert run._value(_figure("x", 690998), "thousands") == "690,998"
    assert Decimal(146041028) / 1000 == Decimal("146041.028")  # el CSV guarda el exacto
