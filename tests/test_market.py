"""Precios de mercado bajados a mano: el CSV, sus comprobaciones y la plantilla. Sin red."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from pitch_to_balance_sheet import market
from pitch_to_balance_sheet.config import ROOT, Club, load_clubs

FIXTURE = Path(__file__).parent / "fixtures" / "precios_manuales_sinteticos.csv"
CLUBS = [
    Club("sint", "Sintético", "", None, "06-30", "IFRS", "SINT.MI", "Bolsa sintética", "EUR"),
    Club("sintl", "Sintético L", "", None, "06-30", "IFRS", "SINT.L", "Bolsa de Londres", "GBp",
         100),
    Club("otro", "No cotizado", "", None, "06-30", "FRS 102"),
]
CONFIG = market.MarketConfig("2030/31", date(2031, 6, 30), "manual/precios.csv",
                             "config/plantillas/precios.csv",
                             {"SINT.L": "sin negociación el 30/06/2031"})


def test_lee_cada_precio_con_su_fuente_y_marca_el_cierre_anterior_y_el_iliquido():
    prices = market.load_prices(FIXTURE, CLUBS, CONFIG)
    sint = prices["sint"]
    # El 30/06/2031 es lunes: el cierre es del viernes 27.
    assert (sint.date, sint.close, sint.currency, sint.unit) == (date(2031, 6, 27),
                                                                 Decimal("1.08"), "EUR", "EUR")
    assert sint.source_url == "https://bolsa.invalid/sint/historico"
    assert "último día de cotización antes del 30/06/2031" in sint.note and not sint.illiquid
    london = prices["sintl"]
    assert (london.close, london.unit, london.currency) == (Decimal("195"), "GBp", "GBP")
    assert london.illiquid == "sin negociación el 30/06/2031"
    assert london.note == "cierre oficial; ilíquido: sin negociación el 30/06/2031"


def _write(tmp_path, rows):
    path = tmp_path / "precios.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=market.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _rows():
    with FIXTURE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize(("change", "error"), [
    ({"close": ""}, "sin rellenar: close"),
    ({"source_url": "bolsa.invalid"}, "source_url tiene que ser una URL"),
    ({"unit": "GBP", "currency": "GBP"}, "la unidad es GBP y SINT.L cotiza en GBp"),
    ({"currency": "EUR"}, "la moneda de GBp es GBP, no EUR"),
    ({"date": "2031-07-01"}, "después de la fecha de valoración"),
    ({"date": "2031-06-20"}, "más de 5 días antes"),
    ({"close": "-1"}, "positivo"),
])
def test_una_fila_mal_rellenada_es_error_y_dice_de_donde_sacar_los_precios(tmp_path, change,
                                                                            error):
    rows = _rows()
    rows[1] = rows[1] | change
    with pytest.raises(market.MarketError, match=error) as caught:
        market.load_prices(_write(tmp_path, rows), CLUBS, CONFIG)
    assert "- SINT.L (Sintético L): cierre del 30/06/2031" in str(caught.value)


def test_faltan_tickers_o_sobran_o_se_repiten(tmp_path):
    rows = _rows()
    with pytest.raises(market.MarketError, match="faltan: SINT.L"):
        market.load_prices(_write(tmp_path, rows[:1]), CLUBS, CONFIG)
    with pytest.raises(market.MarketError, match="tickers repetidos: SINT.MI"):
        market.load_prices(_write(tmp_path, rows + rows[:1]), CLUBS, CONFIG)
    with pytest.raises(market.MarketError, match="no están en config/clubs.yaml: OTRO.MI"):
        market.load_prices(_write(tmp_path, rows + [rows[0] | {"ticker": "OTRO.MI"}]), CLUBS,
                           CONFIG)


def test_sin_el_archivo_dice_que_copiar_y_de_donde_sacar_cada_precio(tmp_path):
    with pytest.raises(market.MarketError) as caught:
        market.load_prices(tmp_path / "no_existe.csv", CLUBS, CONFIG)
    message = str(caught.value)
    assert "Copia la plantilla config/plantillas/precios.csv" in message
    assert "register-manual" in message
    assert ("- SINT.L (Sintético L): cierre del 30/06/2031 (o del último día de cotización "
            "anterior) en Bolsa de Londres, en GBp (peniques)") in message
    assert "No cotizado" not in message


def test_la_plantilla_tiene_los_8_tickers_y_las_columnas_vacias():
    config = market.load_config("2024/25")
    assert (config.valuation_date, config.prices_file) == (date(2025, 6, 30),
                                                           "manual/prices_2025-06-30.csv")
    assert config.illiquid == {"FCP.LS": "sin negociación el 30/06/2025 (volumen 0)"}
    with (ROOT / config.template).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert reader.fieldnames == market.COLUMNS
    tickers = [club.ticker for club in load_clubs() if club.ticker]
    assert [row["ticker"] for row in rows] == tickers and len(tickers) == 8
    assert all(value == "" for row in rows for key, value in row.items() if key != "ticker")
    # Una plantilla sin rellenar no se puede usar.
    with pytest.raises(market.MarketError, match="sin rellenar"):
        market.load_prices(ROOT / config.template, load_clubs(), config)


def test_los_peniques_son_libras():
    assert market.iso_currency("GBp") == "GBP" and market.iso_currency("USD") == "USD"
