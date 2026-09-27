"""Manifiesto de descargas y convenciones de temporada."""

import csv
from datetime import date

import pytest

from pitch_to_balance_sheet.config import fiscal_year_end_date, load_clubs
from pitch_to_balance_sheet.manifest import (
    ManifestEntry,
    ManifestError,
    sha256_bytes,
    upsert,
    verify,
)
from pitch_to_balance_sheet.sources.config import load_sources


def entry(file, sha256="0" * 64):
    return ManifestEntry(file, "https://ejemplo/doc", "2026-09-26T10:00:00+00:00", sha256, 3,
                         "application/pdf")


def test_sha256():
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_upsert_sustituye_la_entrada_del_mismo_archivo_y_ordena(tmp_path):
    path = tmp_path / "manifest.csv"
    upsert(path, [entry("b.pdf"), entry("a.pdf")])
    upsert(path, [entry("b.pdf", sha256="1" * 64)])
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [row["file"] for row in rows] == ["a.pdf", "b.pdf"]
    assert rows[1]["sha256"] == "1" * 64


@pytest.mark.parametrize(
    ("season", "fiscal_year_end", "expected"),
    [("2024/25", "05-31", date(2025, 5, 31)), ("2024/25", "06-30", date(2025, 6, 30))],
)
def test_temporada_es_el_ano_fiscal_que_cierra_en_ella(season, fiscal_year_end, expected):
    assert fiscal_year_end_date(season, fiscal_year_end) == expected


@pytest.mark.parametrize("season", ["2024/26", "2024-25", "24/25"])
def test_temporada_mal_escrita_es_error(season):
    with pytest.raises(ValueError, match="Temporada no válida"):
        fiscal_year_end_date(season, "06-30")


def test_verify_falla_si_falta_no_esta_registrado_o_ha_cambiado(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    with pytest.raises(ManifestError, match="falta data/raw/manual/x.pdf"):
        verify(tmp_path, "manual/x.pdf", manifest_path)
    (tmp_path / "manual").mkdir()
    (tmp_path / "manual" / "x.pdf").write_bytes(b"%PDF-1.4 uno")
    with pytest.raises(ManifestError, match="no está registrado"):
        verify(tmp_path, "manual/x.pdf", manifest_path)
    upsert(manifest_path, [entry("manual/x.pdf", sha256=sha256_bytes(b"%PDF-1.4 uno"))])
    assert verify(tmp_path, "manual/x.pdf", manifest_path)["file"] == "manual/x.pdf"
    (tmp_path / "manual" / "x.pdf").write_bytes(b"%PDF-1.4 dos")
    with pytest.raises(ManifestError, match="ha cambiado"):
        verify(tmp_path, "manual/x.pdf", manifest_path)


def test_sources_yaml_recoge_las_decisiones_del_26_09_2026():
    sources = load_sources("2024/25")
    city = sources["manchester_city"]
    assert (city.primary.kind, city.primary.file) == ("manual", "manual/mancity_2024-25.pdf")
    assert city.primary.url.endswith("mcfc_financial_report_2025_.pdf")
    assert [c.kind for c in city.controls] == ["companies_house"]
    liverpool = sources["liverpool"]
    assert (liverpool.primary.kind, liverpool.primary.file) == ("url", "web/liverpool_2024-25.pdf")
    assert [c.kind for c in liverpool.controls] == ["companies_house"]
    for club_id in ("arsenal", "chelsea", "tottenham", "newcastle"):
        assert sources[club_id].primary.kind == "companies_house"
    juventus = sources["juventus"]
    assert juventus.primary.file == "web/juventus_2024-25_it.pdf"
    assert [c.file for c in juventus.controls] == ["web/juventus_2024-25_en.pdf"]
    assert sources["celtic"].primary.file == "web/celtic_2024-25.pdf"


@pytest.mark.parametrize("kind", ["manual", "url"])
def test_fuente_manual_o_web_sin_archivo_es_error(tmp_path, kind):
    path = tmp_path / "sources.yaml"
    path.write_text(f'"2024/25":\n  x:\n    primary: {{kind: {kind}, url: "https://e.jemplo/x.pdf"}}\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="necesita file"):
        load_sources("2024/25", path)


def test_clubs_yaml_tiene_los_seis_ingleses_y_ocho_cotizados():
    clubs = load_clubs()
    assert [club.club_id for club in clubs] == [
        "arsenal", "chelsea", "liverpool", "manchester_city", "tottenham", "newcastle",
        "juventus", "celtic", "manchester_united", "borussia_dortmund", "ajax", "benfica",
        "lazio", "porto",
    ]
    english = clubs[:6]
    assert all(len(club.companies_house_number) == 8 for club in english)
    assert all(club.fiscal_year_end in ("05-31", "06-30") for club in clubs)


def test_sources_yaml_tiene_las_fuentes_de_las_fases_2d_y_2e():
    sources = load_sources("2024/25")
    for club_id, file in {"ajax": "web/ajax_2024-25.pdf",
                          "benfica": "web/benfica_2024-25.pdf"}.items():
        assert (sources[club_id].primary.kind, sources[club_id].primary.file) == ("url", file)
    united = sources["manchester_united"]
    assert united.primary.url.endswith("2025-mu-plc-form-20-f.pdf")
    assert [c.url.rsplit("/", 1)[-1] for c in united.controls] == ["2026-mu-plc-form-20-f.pdf"]
    dortmund = sources["borussia_dortmund"]
    assert (dortmund.primary.kind, dortmund.primary.file) == (
        "manual", "manual/borussia_dortmund_2024-25_de.pdf")
    assert [c.file for c in dortmund.controls] == ["web/borussia_dortmund_2024-25_en.pdf"]


def test_sources_yaml_tiene_lazio_y_porto():
    sources = load_sources("2024/25")
    lazio = sources["lazio"]
    assert (lazio.primary.kind, lazio.primary.file) == ("url", "web/lazio_2024-25_esef.zip")
    assert "1info.it" in lazio.primary.url and "159386_oneinfo.zip" in lazio.primary.url
    porto = sources["porto"]
    assert (porto.primary.kind, porto.primary.file) == ("manual", "manual/porto_2024-25.pdf")
    assert [(c.kind, c.file) for c in porto.controls] == [
        ("url", "web/porto_comunicado_2024-25.pdf")]
    assert porto.controls[0].url.startswith("https://transparencia.fcporto.pt/")
