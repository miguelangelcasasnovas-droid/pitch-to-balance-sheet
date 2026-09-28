"""Tipos del BCE y conversión a EUR, con un CSV sintético en el formato del BCE: sin red."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from pitch_to_balance_sheet import fx
from pitch_to_balance_sheet.sources.web import download_file

# Días hábiles de junio de 2025, del 0,8000 del día 2 al 0,8200 del día 30, de 0,0010 en 0,0010.
FIXTURE = Path(__file__).parent / "fixtures" / "ecb_exr_d_gbp_eur_sintetico.csv"


@pytest.fixture
def rates():
    return fx.load_rates(FIXTURE, "GBP")


def test_la_media_es_la_de_los_tipos_diarios_del_periodo(rates):
    rate = fx.average_rate(rates, "GBP", date(2025, 6, 1), date(2025, 6, 30))
    assert (rate.rate, rate.method, rate.observations) == (Decimal("0.81"), fx.AVERAGE, 21)
    assert rate.date == "2025-06-01/2025-06-30"
    # Del lunes 9 al viernes 13: 0,8050 a 0,8090, media 0,8070.
    assert fx.average_rate(rates, "GBP", date(2025, 6, 9), date(2025, 6, 13)).rate == Decimal(
        "0.807")


def test_la_media_se_redondea_a_seis_decimales(rates):
    rate = fx.average_rate(rates, "GBP", date(2025, 6, 2), date(2025, 6, 4))
    assert rate.rate == Decimal("0.801000")
    uneven = {day: value for day, value in rates.items() if day != date(2025, 6, 3)}
    rate = fx.average_rate(uneven, "GBP", date(2025, 6, 2), date(2025, 6, 5))
    assert rate.rate == Decimal("0.801667")  # (0,8000 + 0,8020 + 0,8030) / 3 = 0,8016666…


def test_cierre_en_fin_de_semana_toma_el_ultimo_dia_habil_anterior(rates):
    friday = fx.closing_rate(rates, "GBP", date(2025, 6, 27))
    sunday = fx.closing_rate(rates, "GBP", date(2025, 6, 29))
    assert (sunday.rate, sunday.date) == (friday.rate, "2025-06-27") == (Decimal("0.8190"),
                                                                           "2025-06-27")
    assert "último día con tipo antes del cierre (29/06/2025)" in sunday.note
    assert "del día de cierre" in friday.note


def test_sin_tipos_que_cubran_el_periodo_es_error(rates):
    with pytest.raises(fx.FxError, match="no hay tipos entre el 2025-05-01 y el 2025-06-01"):
        fx.average_rate(rates, "GBP", date(2025, 5, 1), date(2025, 6, 30))
    with pytest.raises(fx.FxError, match="no hay tipo ese día ni en los 5 anteriores"):
        fx.closing_rate(rates, "GBP", date(2025, 7, 31))


def test_el_csv_tiene_que_ser_de_la_serie_esperada(tmp_path):
    with pytest.raises(fx.FxError, match="se esperaba EXR.D.USD.EUR.SP00.A"):
        fx.load_rates(FIXTURE, "USD")
    empty = tmp_path / "vacio.csv"
    empty.write_text(FIXTURE.read_text().replace(",0.8100,", ",,"), encoding="utf-8")
    with pytest.raises(fx.FxError, match="el 2025-06-16 no tiene tipo"):
        fx.load_rates(empty, "GBP")
    with pytest.raises(fx.FxError, match="ejecuta download-fx"):
        fx.load_rates(tmp_path / "no_existe.csv", "GBP")


def test_el_importe_en_eur_se_divide_entre_el_tipo_y_se_redondea_al_euro():
    assert fx.to_eur(1_000_000, Decimal("0.8555")) == 1_168_907  # 1.168.907,07…
    assert fx.to_eur(1, Decimal("0.8")) == 1  # 1,25 → 1
    assert fx.to_eur(3, Decimal("2")) == 2  # 1,5 → 2 (mitad hacia arriba)


def test_el_ano_fiscal_va_del_dia_siguiente_al_cierre_anterior_al_cierre():
    assert fx.fiscal_year("2024/25", "05-31") == (date(2024, 6, 1), date(2025, 5, 31))
    assert fx.fiscal_year("2024/25", "06-30") == (date(2024, 7, 1), date(2025, 6, 30))
    assert fx.rates_file("GBP", "2024/25") == "ecb/exr_d_gbp_eur_2024_25.csv"


class _Response:
    def __init__(self, status_code=200, content=b""):
        self.status_code, self.content, self.text = status_code, content, ""


class _Session:
    def get(self, url, headers=None, timeout=None):
        if url.endswith("/robots.txt"):
            return _Response(404)
        return _Response(content=FIXTURE.read_bytes())


def test_la_descarga_acepta_el_csv_del_bce_y_lo_registra(tmp_path):
    url = fx.download_url("GBP", date(2025, 6, 1), date(2025, 6, 30))
    assert url.endswith("D.GBP.EUR.SP00.A?startPeriod=2025-06-01&endPeriod=2025-06-30"
                        "&format=csvdata")
    entry = download_file(url, tmp_path, fx.rates_file("GBP", "2024/25"), session=_Session())
    assert entry.content_type == "text/csv"
    assert len(fx.load_rates(tmp_path / entry.file, "GBP")) == 21
