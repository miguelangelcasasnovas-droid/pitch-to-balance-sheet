"""Football field con un caso calculado a mano. Sin red y sin datos."""

import pandas as pd
import pytest

from pitch_to_balance_sheet import football_field


def test_menos_de_4_transacciones_minimo_mediana_maximo_y_si_no_percentiles():
    assert football_field.stats([3.0, 1.0, 2.0]) == ("mínimo-mediana-máximo", 1.0, 2.0, 3.0)
    # Con 4: posiciones 0,75, 1,5 y 2,25 de 1 2 3 4.
    assert football_field.stats([4.0, 1.0, 3.0, 2.0]) == ("p25-mediana-p75", 1.75, 2.5, 3.25)
    with pytest.raises(football_field.FootballFieldError):
        football_field.stats([])


def _valuation() -> pd.DataFrame:
    rows = []
    for scenario, multiples in (("base", (0.8, 1.2, 2.0)), ("large_peers", (2.0, 3.0, 4.0))):
        rows.append({
            "club_id": "arsenal", "scenario": scenario, "n_peers": 8 if scenario == "base" else 3,
            "peers": "a, b, c", "multiple_p25": multiples[0], "multiple_p50": multiples[1],
            "multiple_p75": multiples[2], "revenue_eur": 1000, "net_debt_eur": 300,
            "ev_implied_p25": int(multiples[0] * 1000), "ev_implied_p50": int(multiples[1] * 1000),
            "ev_implied_p75": int(multiples[2] * 1000),
            "equity_implied_p25": int(multiples[0] * 1000) - 300,
            "equity_implied_p50": int(multiples[1] * 1000) - 300,
            "equity_implied_p75": int(multiples[2] * 1000) - 300,
            "reason": "", "note": "Sin prima de control"})
    return pd.DataFrame(rows)


def _transactions() -> pd.DataFrame:
    rows = [("chelsea", "base", "equity", "equity", 5.5), ("manu", "base", "equity", "per_share",
                                                            7.5),
            ("milan", "base", "equity", "equity", 6.0), ("milan", "base", "ev", "ev", 5.0),
            ("newcastle", "press_only", "equity", "equity", 1.5)]
    return pd.DataFrame([{"deal_id": d, "tier": t, "variant": v, "basis": b,
                          "ev_to_revenue": m, "status": "ok"} for d, t, v, b, m in rows])


def test_football_field_calculado_a_mano():
    frame = football_field.to_frame(
        football_field.build(_valuation(), _transactions(), ["arsenal"], "2024/25"))
    assert football_field.validate(frame) == []
    by_method = frame.set_index("method")
    # Comparables: tal cual de la tabla valuation.
    assert by_method.loc["comparables", ["ev_low", "ev_mid", "ev_high"]].tolist() == [800, 1200,
                                                                                       2000]
    # Transacciones base: 5,5 6,0 7,5 (Milan como equity; Newcastle, solo prensa, fuera):
    # mínimo, mediana y máximo × 1.000 de ingresos; equity, menos 300 de deuda neta.
    transactions = by_method.loc["transactions"]
    assert transactions["statistic"] == "mínimo-mediana-máximo" and transactions["n"] == 3
    assert [transactions[c] for c in ("ev_low", "ev_mid", "ev_high")] == [5500, 6000, 7500]
    assert [transactions[c] for c in ("equity_low", "equity_mid", "equity_high")] == [
        5200, 5700, 7200]
    assert "newcastle" not in transactions["inputs"]
    # Sensibilidad con Milan como EV: 5,0 5,5 7,5.
    milan_ev = by_method.loc["transactions_milan_ev"]
    assert [milan_ev[c] for c in ("ev_low", "ev_mid", "ev_high")] == [5000, 5500, 7500]


def test_una_transaccion_base_sin_variante_de_equity_es_error():
    deals = _transactions()
    deals = deals[deals["deal_id"] != "milan"]
    deals.loc[deals["deal_id"] == "chelsea", "basis"] = "ev"
    with pytest.raises(football_field.FootballFieldError, match="chelsea"):
        football_field.deal_multiples(deals)
