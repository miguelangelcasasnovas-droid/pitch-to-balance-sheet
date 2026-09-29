"""Precios de mercado con un CSV sintético y un yfinance simulado: sin red."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from pitch_to_balance_sheet import market
from pitch_to_balance_sheet.config import Club

FIXTURE = Path(__file__).parent / "fixtures" / "precio_sintetico.csv"  # 26 y 27/06/2031
CLUB = Club("sintetico", "Sintético", "", None, "06-30", "IFRS", "SINT.MI", "EUR")


def test_cierre_del_ultimo_dia_de_cotizacion_anterior_a_la_fecha():
    # El 30/06/2031 es lunes: el último cierre anterior es el del viernes 27.
    price = market.load_price(FIXTURE, CLUB, date(2031, 6, 30))
    assert (price.date, price.close, price.currency) == (date(2031, 6, 27), Decimal("1.08"),
                                                         "EUR")
    assert "último día de cotización antes del 30/06/2031" in price.note
    assert market.load_price(FIXTURE, CLUB, date(2031, 6, 26)).close == Decimal("1.05")


def test_un_cierre_demasiado_antiguo_o_de_otro_valor_es_error():
    with pytest.raises(market.MarketError, match="más de 5 días"):
        market.load_price(FIXTURE, CLUB, date(2031, 7, 10))
    with pytest.raises(market.MarketError, match="no hay cotización"):
        market.load_price(FIXTURE, CLUB, date(2031, 6, 1))
    other = Club("otro", "Otro", "", None, "06-30", "IFRS", "OTRO.MI", "EUR")
    with pytest.raises(market.MarketError, match="no es de OTRO.MI"):
        market.load_price(FIXTURE, other, date(2031, 6, 30))


class _Ticker:
    def __init__(self, ticker, currency="GBp"):
        self.ticker = ticker
        self.history_metadata = {"currency": currency, "exchangeName": "LSE",
                                 "exchangeTimezoneName": "Europe/London"}

    def history(self, start, end, auto_adjust, actions):
        assert not auto_adjust  # el cierre sin ajustar
        index = pd.DatetimeIndex(["2025-06-27", "2025-06-30"]).tz_localize("Europe/London")
        return pd.DataFrame({"Open": [195.0, 195.0], "High": [196.0, 195.0],
                             "Low": [190.0, 195.0], "Close": [195.00000001, 194.9999999],
                             "Adj Close": [195.0, 195.0], "Volume": [3322, 0]}, index=index)


def test_la_descarga_guarda_el_historico_y_su_entrada_del_manifiesto(tmp_path):
    celtic = Club("celtic", "Celtic", "", None, "06-30", "IFRS", "CCP.L", "GBp", 100)
    entry = market.download_price(celtic, tmp_path, ticker_factory=_Ticker)
    assert entry.file == "market/ccp.l_2025-06-30.csv"
    assert entry.url.startswith("https://query2.finance.yahoo.com/v8/finance/chart/CCP.L?")
    price = market.load_price(tmp_path / entry.file, celtic)
    # Se redondea a 4 decimales; el valor de Yahoo queda en close_raw.
    assert (price.close, price.volume) == (Decimal("195.0000"), 0)
    assert "volumen 0" in price.note
    assert "194.9999999" in (tmp_path / entry.file).read_text()


def test_si_la_moneda_no_es_la_esperada_es_error(tmp_path):
    celtic = Club("celtic", "Celtic", "", None, "06-30", "IFRS", "CCP.L", "GBP")
    with pytest.raises(market.MarketError, match="moneda 'GBp'"):
        market.download_price(celtic, tmp_path, ticker_factory=_Ticker)


def test_los_peniques_son_libras():
    assert market.iso_currency("GBp") == "GBP" and market.iso_currency("USD") == "USD"
