"""Métricas con cifras sintéticas en EUR, calculadas a mano. Sin red y sin datos."""

import pandas as pd
import pytest

from pitch_to_balance_sheet import metrics


def _fact(club_id, concept, value_eur=None, gap_reason=""):
    return {"club_id": club_id, "season": "2024/25", "concept": concept,
            "value_eur": value_eur, "is_gap": value_eur is None, "gap_reason": gap_reason}


def _frame(club_id="juventus", **changes):
    values = {"revenue_ex_player_trading": 1_000_000, "revenue_matchday": 200_000,
              "revenue_broadcasting": 450_000, "revenue_commercial": 300_000,
              "revenue_other": 50_000, "staff_costs": 600_000, "borrowings": 500_000,
              "cash": 100_000, "lease_liabilities": 50_000, "transfer_payables": 300_000,
              "transfer_receivables": 120_000} | changes
    rows = [_fact(club_id, concept, value, "no se publica" if value is None else "")
            for concept, value in values.items()]
    return pd.DataFrame(rows).astype({"value_eur": "Int64"})


def _by_name(frame):
    return {m.metric: m for m in metrics.compute(frame)}


def test_mix_salarios_y_deudas_netas_calculados_a_mano():
    found = _by_name(_frame())
    # Mix: 200.000 / 1.000.000, 450.000 / 1.000.000...
    assert [found[f"mix_{k}"].value for k in ("matchday", "broadcasting", "commercial",
                                              "other")] == [0.2, 0.45, 0.3, 0.05]
    assert found["staff_to_revenue"].value == 0.6  # 600.000 / 1.000.000
    # net_debt = 500.000 − 100.000; con arrendamientos, + 50.000; con traspasos, + 300.000 −
    # 120.000.
    assert (found["net_debt"].value, found["net_debt_incl_leases"].value,
            found["net_debt_incl_transfers"].value) == (400_000, 450_000, 580_000)
    assert (found["net_debt_to_revenue"].value, found["net_debt_incl_leases_to_revenue"].value,
            found["net_debt_incl_transfers_to_revenue"].value) == (0.4, 0.45, 0.58)
    assert found["net_debt"].components == "borrowings 500,000 − cash 100,000"
    assert "net_debt_incl_related_party" not in found  # solo con related_party_financing


def test_en_frs_102_la_deuda_con_arrendamientos_es_no_comparable_no_cero():
    found = _by_name(_frame("arsenal", lease_liabilities=0))  # Arsenal: FRS 102
    for name in ("net_debt_incl_leases", "net_debt_incl_leases_to_revenue"):
        assert found[name].status == metrics.NOT_COMPARABLE and found[name].value is None
        assert "FRS 102" in found[name].reason
    assert found["net_debt"].value == 400_000  # la principal no lleva arrendamientos


def test_un_hueco_deja_la_metrica_en_hueco_y_dice_cual():
    found = _by_name(_frame(transfer_payables=None))
    transfers = found["net_debt_incl_transfers"]
    assert transfers.status == metrics.GAP and transfers.value is None
    assert transfers.reason == "falta transfer_payables (no se publica)"
    assert found["net_debt_incl_transfers_to_revenue"].reason == transfers.reason
    assert found["net_debt"].status == metrics.OK


def test_deuda_con_saldos_vinculados_solo_si_el_club_los_tiene():
    found = _by_name(_frame(related_party_financing=150_000))
    assert found["net_debt_incl_related_party"].value == 550_000  # 400.000 + 150.000


def test_el_scr_queda_como_hueco_con_su_motivo():
    scr = _by_name(_frame())["scr_approx"]
    assert (scr.status, scr.value, scr.reason) == (
        metrics.GAP, None, "faltan 2022/23 y 2023/24 para el promedio de traspasos a 3 años")


def test_pandera_valida_las_metricas():
    frame = metrics.to_frame(metrics.compute(_frame()))
    assert metrics.validate(frame) == []
    frame.loc[frame["metric"] == "scr_approx", "reason"] = ""
    assert any("motivo" in problem for problem in metrics.validate(frame))


@pytest.mark.parametrize("revenue", [None, 0])
def test_sin_ingresos_los_ratios_son_hueco(revenue):
    found = _by_name(_frame(revenue_ex_player_trading=revenue))
    assert found["staff_to_revenue"].status == metrics.GAP
    assert found["net_debt"].status == metrics.OK
