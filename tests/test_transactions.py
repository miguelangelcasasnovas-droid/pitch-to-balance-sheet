"""Transacciones precedentes: configuración, EV y múltiplos con casos calculados a mano. Sin red."""

from datetime import date
from decimal import Decimal

import pytest
import yaml

from pitch_to_balance_sheet import transactions
from pitch_to_balance_sheet.extract.references import REFERENCE_SPECS
from pitch_to_balance_sheet.sources.config import load_sources


def _deal(**changes) -> dict:
    deal = {
        "deal_id": "sint_2030", "club_id": "sint", "name": "Sintético", "tier": "base",
        "announced": "2030-05-07", "price_currency": "GBP", "price_primary": True,
        "price_source": "https://club.invalid/nota", "price_text": "«£100m for the shares»",
        "variants": [{"variant": "equity", "basis": "equity", "amount": "100000000"}],
        "reference": {"season": "2028/29", "published": "2029-12-29",
                      "evidence": "Companies House: depositadas el 29/12/2029"},
    }
    return deal | changes


def _load(tmp_path, *deals) -> list[transactions.Deal]:
    path = tmp_path / "transactions.yaml"
    path.write_text(yaml.safe_dump({"deals": list(deals)}), encoding="utf-8")
    return transactions.load_deals(path)


def _financials(**changes) -> transactions.Financials:
    values = {"currency": "GBP", "period_end": date(2029, 6, 30),
              "revenue_ex_player_trading": 50_000_000, "borrowings": 30_000_000,
              "cash": 10_000_000}
    return transactions.Financials(**(values | changes))


def test_equity_ev_y_multiplo_calculados_a_mano(tmp_path):
    deals = _load(tmp_path, _deal(variants=[
        {"variant": "equity", "basis": "equity", "amount": "100000000"},
        {"variant": "ev", "basis": "ev", "amount": "100000000"}]))
    rows = transactions.compute(deals, {"sint_2030": _financials()})
    equity, ev = rows
    # Deuda neta 30 − 10 = 20 millones. Como equity: EV 120, múltiplo 120 / 50 = 2,4.
    assert (equity.equity_value, equity.net_debt, equity.ev) == (100_000_000, 20_000_000,
                                                                 120_000_000)
    assert equity.ev_to_revenue == pytest.approx(2.4)
    # Como EV: EV 100, equity implícito 80, múltiplo 2,0.
    assert (ev.ev, ev.equity_value, ev.ev_to_revenue) == (100_000_000, 80_000_000, 2.0)
    frame = transactions.to_frame(rows)
    assert transactions.validate(frame) == []
    assert (frame["marks"] == "").all()


def test_precio_por_accion_por_todas_las_acciones_y_en_la_moneda_de_las_cuentas(tmp_path):
    deals = _load(tmp_path, _deal(price_currency="USD", variants=[
        {"variant": "equity", "basis": "per_share", "price_per_share": "33.00"}]))
    usd = {date(2030, 5, 3): Decimal("1.10")}
    gbp = {date(2030, 5, 3): Decimal("0.88")}
    # El 07/05/2030 es martes; el último tipo es del viernes 3: 4 días antes, dentro del margen.
    rate = transactions.cross_rate(usd, gbp, "USD", "GBP", date(2030, 5, 7))
    assert rate.rate == Decimal("0.8") and rate.date == "2030-05-03"
    assert "último día con tipo antes del anuncio del 07/05/2030" in rate.note
    rows = transactions.compute(
        deals, {"sint_2030": _financials(shares_outstanding=1_000_000)}, {"sint_2030": rate})
    row = rows[0]
    # 33 × 1.000.000 = 33 millones de USD; × 0,8 = 26,4 millones de GBP; + 20 de deuda neta.
    assert (row.price_amount, row.equity_value, row.ev) == (33_000_000, 26_400_000, 46_400_000)
    assert row.currency == "GBP" and row.fx_rate == 0.8


def test_sin_tipos_o_sin_acciones_es_error(tmp_path):
    usd_deal = _load(tmp_path, _deal(price_currency="USD"))
    with pytest.raises(transactions.TransactionsError, match="faltan los tipos del BCE"):
        transactions.compute(usd_deal, {"sint_2030": _financials()})
    per_share = _load(tmp_path, _deal(variants=[
        {"variant": "equity", "basis": "per_share", "price_per_share": "1"}]))
    with pytest.raises(transactions.TransactionsError, match="faltan las acciones"):
        transactions.compute(per_share, {"sint_2030": _financials()})


def test_solo_prensa_marcada_y_excluidas_y_pendientes_con_motivo(tmp_path):
    deals = _load(
        tmp_path,
        _deal(deal_id="prensa", tier="press_only", price_primary=False),
        _deal(deal_id="pendiente", tier="press_only", price_primary=False),
        {"deal_id": "fuera", "name": "Multiclub", "tier": "excluded", "announced": "2030-01-01",
         "price_currency": "USD", "price_source": "https://x.invalid", "price_text": "500 M",
         "reason": "grupo multiclub", "variants": []})
    rows = transactions.compute(deals, {"prensa": _financials()},
                                pending={"pendiente": "sin fuente accesible"})
    frame = transactions.to_frame(rows).set_index("deal_id")
    assert transactions.validate(frame.reset_index()) == []
    assert frame.loc["prensa", "marks"] == transactions.PRESS_ONLY_MARK
    assert frame.loc["pendiente", "status"] == "pending"
    assert frame.loc["pendiente", "reason"] == "sin fuente accesible"
    assert frame.loc["fuera", "status"] == "excluded"


@pytest.mark.parametrize(("change", "error"), [
    ({"reference": {"season": "2029/30", "published": "2030-06-01", "evidence": "x"}},
     "después del anuncio"),
    ({"price_primary": False}, "fuente primaria"),
    ({"tier": "press_only"}, "no es press_only"),
    ({"variants": [{"variant": "equity", "basis": "per_share", "amount": "1"}]},
     "per_share lleva price_per_share"),
    ({"tier": "otro"}, "tier"),
])
def test_configuracion_no_valida(tmp_path, change, error):
    with pytest.raises(transactions.TransactionsError, match=error):
        _load(tmp_path, _deal(**change))


def test_las_cuentas_de_referencia_no_pueden_cerrar_despues_del_anuncio(tmp_path):
    deals = _load(tmp_path, _deal())
    with pytest.raises(transactions.TransactionsError, match="no antes del anuncio"):
        transactions.compute(deals, {"sint_2030": _financials(period_end=date(2030, 6, 30))})


def test_config_de_las_operaciones_del_usuario():
    deals = {deal.deal_id: deal for deal in transactions.load_deals()}
    tiers = {deal_id: deal.tier for deal_id, deal in deals.items()}
    assert tiers == {"chelsea_2022": "base", "manchester_united_2024": "base",
                     "milan_2022": "base", "newcastle_2021": "press_only",
                     "everton_2024": "press_only", "roma_2020": "press_only",
                     "city_football_group_2019": "excluded", "inter_2024": "excluded"}
    assert deals["chelsea_2022"].variants[0].amount == Decimal("2500000000")
    assert deals["manchester_united_2024"].variants[0].price_per_share == Decimal("33.00")
    assert [v.basis for v in deals["milan_2022"].variants] == ["equity", "ev"]
    assert "1.750" in deals["chelsea_2022"].note  # la inversión comprometida, aparte
    clubs = transactions.all_clubs()
    for deal in deals.values():
        if deal.tier == "excluded":
            assert deal.reason
            continue
        # Cada operación tiene su fuente, su extractor y cuentas cerradas antes del anuncio.
        season = deal.reference.season
        source = load_sources(season)[deal.club_id].primary
        assert (deal.club_id, season) in REFERENCE_SPECS
        assert transactions.period_end(deal, clubs[deal.club_id],
                                       source.made_up_date) < deal.reference.published
    assert transactions.period_end(deals["newcastle_2021"], clubs["newcastle"],
                                   "2020-07-31") == date(2020, 7, 31)
