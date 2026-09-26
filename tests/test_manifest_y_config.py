"""Manifiesto de descargas y convenciones de temporada."""

import csv
from datetime import date

import pytest

from pitch_to_balance_sheet.config import fiscal_year_end_date, load_clubs
from pitch_to_balance_sheet.manifest import ManifestEntry, sha256_bytes, upsert


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


def test_clubs_yaml_tiene_los_seis_ingleses():
    clubs = load_clubs()
    assert [club.club_id for club in clubs] == [
        "arsenal", "chelsea", "liverpool", "manchester_city", "tottenham", "newcastle",
    ]
    assert all(len(club.companies_house_number) == 8 for club in clubs)
