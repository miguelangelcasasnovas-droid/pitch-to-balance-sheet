"""Valoración por comparables con un caso calculado a mano. Sin red y sin datos."""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from pitch_to_balance_sheet import metrics, valuation
from pitch_to_balance_sheet.config import Club
from pitch_to_balance_sheet.market import Price

DAY = date(2025, 6, 30)


def test_percentiles_con_interpolacion_lineal():
    # Con 4 valores, las posiciones son 3 × 0,25 = 0,75, 1,5 y 2,25.
    values = [3.0, 1.0, 4.0, 2.0]
    assert [valuation.quantile(values, q) for q in (0.25, 0.5, 0.75)] == [1.75, 2.5, 3.25]
    assert valuation.quantile([5.0], 0.75) == 5.0
    with pytest.raises(valuation.ValuationError):
        valuation.quantile([], 0.5)


def _price(close, currency):
    return Price("X", DAY, Decimal(close), currency, 100, "x.csv", "cierre del día de valoración")


def test_precio_en_eur_con_el_tipo_del_mismo_dia_y_peniques_entre_100():
    rates = {"GBP": {DAY: Decimal("0.8555")}, "USD": {DAY: Decimal("1.172")}}
    celtic = Club("celtic", "Celtic", "", None, "06-30", "IFRS", "CCP.L", "GBp", 100)
    q = valuation.quote(celtic, _price("195", "GBp"), 1000, rates)
    # 195 peniques = 1,95 libras; 1,95 / 0,8555 = 2,27937... euros; × 1.000 acciones.
    assert (round(q.price_eur, 5), q.market_cap_eur, q.fx_date) == (Decimal("2.27937"), 2279,
                                                                    "2025-06-30")
    manu = Club("manchester_united", "MU", "", None, "06-30", "IFRS", "MANU", "USD")
    q = valuation.quote(manu, _price("17.81", "USD"), 100, rates)
    assert q.market_cap_eur == 1520  # 17,81 / 1,172 = 15,1962... × 100
    juve = Club("juventus", "J", "", None, "06-30", "IFRS", "JUVE.MI", "EUR")
    q = valuation.quote(juve, _price("3.088", "EUR"), 1000, rates)
    assert (q.fx_rate, q.market_cap_eur) == (1, 3088)


LISTED = {  # club: (capitalización, deuda neta, ingresos), en EUR
    "juventus": (1000, 200, 400),  # EV 1.200, múltiplo 3,0
    "ajax": (300, -50, 500),  # EV 250, múltiplo 0,5
    "benfica": (150, 150, 200),  # EV 300, múltiplo 1,5
    "lazio": (100, 20, 120),  # EV 120, múltiplo 1,0
}


def _inputs():
    facts = [{"club_id": club_id, "season": "2024/25",
              "concept": "revenue_ex_player_trading", "value_eur": revenue, "is_gap": False}
             for club_id, (_, _, revenue) in LISTED.items()]
    facts.append({"club_id": "arsenal", "season": "2024/25",
                  "concept": "revenue_ex_player_trading", "value_eur": 1000, "is_gap": False})
    rows = [metrics.Metric(club_id, "2024/25", "net_debt", float(net_debt), "EUR", "ok", "",
                           "", "") for club_id, (_, net_debt, _) in LISTED.items()]
    rows.append(metrics.Metric("arsenal", "2024/25", "net_debt", 300.0, "EUR", "ok", "", "", ""))
    # Con traspasos netos, 100 más de deuda en cada club; Lazio no tiene el dato.
    rows += [metrics.Metric(club_id, "2024/25", "net_debt_incl_transfers", float(net_debt + 100),
                            "EUR", "ok", "", "", "")
             for club_id, (_, net_debt, _) in LISTED.items() if club_id != "lazio"]
    rows.append(metrics.Metric("lazio", "2024/25", "net_debt_incl_transfers", None, "EUR", "gap",
                               "falta transfer_payables (no se publica)", "", ""))
    quotes = {club_id: valuation.Quote(club_id, _price("1", "EUR"), 1, Decimal(1), "", "",
                                       cap, Decimal(1), cap)
              for club_id, (cap, _, _) in LISTED.items()}
    return pd.DataFrame(facts), metrics.to_frame(rows), quotes


def test_valoracion_por_comparables_calculada_a_mano():
    facts, metric_frame, quotes = _inputs()
    frame = valuation.to_frame(valuation.run(facts, metric_frame, quotes))
    assert valuation.validate(frame) == []
    base = frame[frame["scenario"] == "base"].set_index("club_id")
    assert base.loc["juventus", "ev_eur"] == 1200 and base.loc["juventus", "ev_to_revenue"] == 3.0
    # Múltiplos ordenados 0,5 1,0 1,5 3,0: P25 = 0,5 + 0,75 × 0,5 = 0,875; mediana = 1,25; P75 =
    # 1,5 + 0,25 × 1,5 = 1,875.
    arsenal = base.loc["arsenal"]
    assert (arsenal["multiple_p25"], arsenal["multiple_p50"], arsenal["multiple_p75"]) == (
        0.875, 1.25, 1.875)
    # Arsenal, ingresos 1.000 y deuda neta 300: EV 875 / 1.250 / 1.875 y equity 575 / 950 / 1.575.
    assert [arsenal[f"ev_implied_{p}"] for p in ("p25", "p50", "p75")] == [875, 1250, 1875]
    assert [arsenal[f"equity_implied_{p}"] for p in ("p25", "p50", "p75")] == [575, 950, 1575]
    assert "Sin prima de control" in arsenal["note"]
    # Prueba sobre Juventus: EV real 1.200 frente a 1,25 × 400 = 500: +140 %, fuera de 350–750.
    # Sin la propia Juventus, la mediana de 0,5 1,0 1,5 es 1,0: 400, +200 %.
    juventus = base.loc["juventus"]
    assert juventus["ev_implied_p50"] == 500
    assert juventus["deviation_vs_p50"] == pytest.approx(1.4)
    assert not juventus["within_p25_p75"]
    assert juventus["multiple_p50_excl_self"] == 1.0
    assert juventus["deviation_vs_p50_excl_self"] == pytest.approx(2.0)


def test_solo_pares_grandes_y_un_par_sin_dato_sale_del_calculo():
    facts, metric_frame, quotes = _inputs()
    frame = valuation.to_frame(valuation.run(facts, metric_frame, quotes)).set_index(
        ["scenario", "club_id"])
    # Entre los pares grandes solo está Juventus: todos los percentiles son su múltiplo, 3,0.
    assert frame.loc[("large_peers", "arsenal"), "ev_implied_p50"] == 3000
    # Con traspasos netos, Lazio sale del cálculo: múltiplos (1.200 + 100) / 400 = 3,25,
    # (250 + 100) / 500 = 0,7 y (300 + 100) / 200 = 2,0; la mediana es 2,0.
    lazio = frame.loc[("incl_transfers", "lazio")]
    assert lazio["status"] == "gap" and pd.isna(lazio["ev_eur"])
    arsenal = frame.loc[("incl_transfers", "arsenal")]
    assert arsenal["n_peers"] == 3 and "fuera: lazio" in arsenal["peers"]
    assert arsenal["multiple_p50"] == 2.0
    # Arsenal no tiene deuda con traspasos: su EV implícito se calcula, su equity no.
    assert arsenal["ev_implied_p50"] == 2000 and pd.isna(arsenal["equity_implied_p50"])
    assert arsenal["status"] == "gap"


def test_un_escenario_sin_ningun_par_con_datos_es_error():
    facts, metric_frame, quotes = _inputs()
    metric_frame = metric_frame[metric_frame["metric"] != "net_debt_incl_transfers"]
    with pytest.raises(valuation.ValuationError, match="no hay múltiplos"):
        valuation.run(facts, metric_frame, quotes)


def test_sin_cotizacion_de_un_cotizado_es_error():
    facts, metric_frame, quotes = _inputs()
    del quotes["ajax"]
    with pytest.raises(valuation.ValuationError, match="ajax: falta su cotización"):
        valuation.run(facts, metric_frame, quotes)
