"""fact_financials con cifras y tipos sintéticos: conversión, validación con pandera, guardado en
parquet y DuckDB, y tabla resumen. Sin red y sin los PDFs."""

import csv
from datetime import date, timedelta
from decimal import Decimal

import duckdb
import pandas as pd
import pytest

from pitch_to_balance_sheet import facts, fx, manifest

SEASON = "2024/25"
SHA = "a" * 64
HEADER = open(  # la cabecera real del CSV del BCE (format=csvdata)
    __file__.replace("test_facts.py", "fixtures/ecb_exr_d_gbp_eur_sintetico.csv"),
    encoding="utf-8").readline().rstrip("\n")


def _rates(raw_dir):
    """Tipos sintéticos de días hábiles, de junio de 2024 a junio de 2025: 0,8 hasta el 29 de
    junio de 2025 y 0,9 el 30 (el cierre), para distinguir media y cierre."""
    lines, day = [HEADER], date(2024, 6, 3)
    while day <= date(2025, 6, 30):
        if day.weekday() < 5:
            rate = "0.9" if day == date(2025, 6, 30) else "0.8"
            lines.append(f"EXR.D.GBP.EUR.SP00.A,D,GBP,EUR,SP00,A,{day.isoformat()},{rate},A,F,,,"
                         "P1D,,A,,,,,,,99Q1=100,,,5,,4F0,,Sintético,Sintético,GBP,0")
        day += timedelta(days=1)
    path = raw_dir / fx.rates_file("GBP", SEASON)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _row(club_id, concept, value, currency="GBP", unit="thousands", **changes):
    multiplier = {"thousands": 1000, "shares": 1}[unit]
    row = {
        "club_id": club_id, "season": SEASON, "fiscal_year_end": "2025-06-30",
        "concept": concept, "value_reported": str(value), "unit_reported": unit,
        "currency_reported": currency, "value_full": str(value * multiplier),
        "is_gap": "False", "gap_reason": "", "is_derived": "False",
        "included_in_staff_costs": "", "components": f"+ pág. 1 {concept!r} [2025] {value}",
        "source": "Companies House", "source_file": f"x/{club_id}.pdf", "source_page": "1",
        "label_original": concept, "column": "2025", "sha256": SHA,
        "extraction_method": "texto", "ocr_note": "", "ocr_raw": "", "definition_note": "",
        "crop": "", "status": "ok",
    }
    return row | changes


def _gap(club_id, concept, reason="no se publica"):
    return _row(club_id, concept, 0, value_reported="", value_full="", is_gap="True",
                gap_reason=reason, components="", source_page="")


MIX = {"revenue_matchday": 100, "revenue_broadcasting": 500, "revenue_commercial": 380,
       "revenue_other": 20}


def _rows():
    chelsea = [_row("chelsea", "revenue_ex_player_trading", 1000),
               *(_row("chelsea", concept, value) for concept, value in MIX.items()),
               _row("chelsea", "staff_costs", 600), _row("chelsea", "borrowings", 90),
               _row("chelsea", "cash", 30), _gap("chelsea", "lease_liabilities"),
               _gap("chelsea", "transfer_payables"), _gap("chelsea", "transfer_receivables")]
    juventus = [_row("juventus", "revenue_ex_player_trading", 400, "EUR"),
                _row("juventus", "staff_costs", 200, "EUR"),
                _row("juventus", "borrowings", 300, "EUR"),
                _row("juventus", "lease_liabilities", 10, "EUR"),
                _row("juventus", "cash", 40, "EUR"),
                _row("juventus", "transfer_payables", 220, "EUR"),
                _row("juventus", "transfer_receivables", 100, "EUR"),
                _row("juventus", "shares_outstanding", 379121815, "EUR", "shares")]
    return chelsea + juventus


@pytest.fixture
def setup(tmp_path):
    raw_dir = tmp_path / "raw"
    rates = _rates(raw_dir)
    manifest_path = raw_dir / "manifest.csv"
    entries = [manifest.ManifestEntry(fx.rates_file("GBP", SEASON), "https://ecb.invalid",
                                      "2026-09-28T10:00:00+00:00",
                                      manifest.sha256_file(rates), rates.stat().st_size,
                                      "text/csv")]
    entries += [manifest.ManifestEntry(f"x/{club}.pdf", f"https://{club}.invalid",
                                       "2026-09-26T10:00:00+00:00", SHA, 1, "application/pdf")
                for club in ("chelsea", "juventus")]
    manifest.upsert(manifest_path, entries)
    return tmp_path, raw_dir, manifest_path


def _build(setup, rows):
    tmp_path, raw_dir, manifest_path = setup
    path = tmp_path / "cifras.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return facts.build(SEASON, path, raw_dir, manifest_path)


def _fact(frame, club_id, concept):
    return frame[(frame["club_id"] == club_id) & (frame["concept"] == concept)].iloc[0]


def test_convierte_con_la_media_del_ano_fiscal_y_con_el_tipo_de_cierre(setup):
    frame = _build(setup, _rows())
    assert facts.validate(frame) == []
    staff = _fact(frame, "chelsea", "staff_costs")
    assert staff["fx_method"] == fx.AVERAGE and staff["fx_date"] == "2024-07-01/2025-06-30"
    # Todos los días hábiles del año fiscal a 0,8 y el 30 de junio a 0,9: la media, a 6
    # decimales.
    days = sum((date(2024, 7, 1) + timedelta(n)).weekday() < 5 for n in range(365))
    average = (Decimal("0.8") * (days - 1) + Decimal("0.9")) / days
    assert Decimal(str(staff["fx_rate"])) == average.quantize(Decimal("0.000001"))
    assert staff["value_eur"] == fx.to_eur(600_000, Decimal(str(staff["fx_rate"])))
    cash = _fact(frame, "chelsea", "cash")
    assert (cash["fx_method"], cash["fx_date"], cash["fx_rate"]) == (fx.CLOSING, "2025-06-30",
                                                                    0.9)
    assert cash["value_eur"] == 33_333  # 30.000 / 0,9
    assert cash["source_url"] == "https://chelsea.invalid"
    assert cash["fx_source_file"] == "ecb/exr_d_gbp_eur_2024_25.csv"


def test_eur_sin_conversion_y_acciones_sin_tipo(setup):
    frame = _build(setup, _rows())
    borrowings = _fact(frame, "juventus", "borrowings")
    assert (borrowings["fx_rate"], borrowings["fx_method"], borrowings["value_eur"]) == (
        1.0, fx.NO_CONVERSION, 300_000)
    shares = _fact(frame, "juventus", "shares_outstanding")
    assert shares["fx_method"] == fx.NOT_MONETARY and shares["currency_reported"] == ""
    assert shares["value_full"] == 379121815
    assert pd.isna(shares["value_eur"])


def test_un_hueco_va_sin_valor_con_su_motivo_y_sin_conversion(setup):
    frame = _build(setup, _rows())
    gap = _fact(frame, "chelsea", "lease_liabilities")
    assert gap["is_gap"] and gap["gap_reason"] == "no se publica"
    assert pd.isna(gap["value_reported"]) and gap["fx_method"] == ""


def test_pandera_rechaza_conversion_mal_hecha_cifra_sin_fuente_y_hueco_sin_motivo(setup):
    frame = _build(setup, _rows())
    frame.loc[frame["concept"] == "cash", "value_eur"] = 1
    frame.loc[frame["concept"] == "staff_costs", "source_page"] = None
    frame.loc[frame["is_gap"], "gap_reason"] = ""
    problems = " | ".join(facts.validate(frame))
    assert "value_eur no es value_full / fx_rate" in problems
    assert "una cifra tiene que llevar su valor y su fuente" in problems
    assert "un hueco va sin valor y con su motivo" in problems


def test_pandera_rechaza_la_clave_repetida(setup):
    frame = _build(setup, _rows())
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    assert any("clave repetida" in problem for problem in facts.validate(frame))


def test_pandera_comprueba_que_el_reparto_suma_los_ingresos(setup):
    rows = [row | ({"value_reported": "150", "value_full": "150000"}
                   if row["concept"] == "revenue_other" and row["club_id"] == "chelsea" else {})
            for row in _rows()]
    assert any("revenue_ex_player_trading" in problem
               for problem in facts.validate(_build(setup, rows)))


@pytest.mark.parametrize(("change", "error"), [
    ({"status": "error"}, "está en error"),
    ({"concept": "ebitda"}, "fuera de la lista cerrada"),
    ({"sha256": "b" * 64}, "sha256"),
])
def test_no_se_construye_si_la_extraccion_esta_mal(setup, change, error):
    rows = _rows()
    rows[0] = rows[0] | change
    with pytest.raises(facts.FactsError, match=error):
        _build(setup, rows)


def test_sin_los_tipos_del_bce_es_error(setup):
    _, raw_dir, _ = setup
    (raw_dir / fx.rates_file("GBP", SEASON)).unlink()
    with pytest.raises(facts.FactsError, match="download-fx"):
        _build(setup, _rows())


def test_guarda_parquet_y_duckdb_y_sustituye_la_temporada(setup):
    tmp_path = setup[0]
    frame = _build(setup, _rows())
    out = tmp_path / "processed"
    parquet, database = facts.write(frame, SEASON, out)
    facts.write(frame, SEASON, out)  # otra vez: no duplica
    with duckdb.connect(str(database)) as con:
        assert con.execute("SELECT count(*) FROM fact_financials").fetchone()[0] == len(frame)
        assert con.execute(f"SELECT count(*) FROM '{parquet}'").fetchone()[0] == len(frame)
        cash = con.execute("SELECT value_eur, fx_method FROM fact_financials WHERE "
                           "club_id = 'chelsea' AND concept = 'cash'").fetchone()
    assert cash == (33_333, fx.CLOSING)
