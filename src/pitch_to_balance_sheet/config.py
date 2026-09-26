"""Lectura de config/ y convenciones de temporada."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


@dataclass(frozen=True)
class Club:
    club_id: str
    name: str
    entity: str
    companies_house_number: str
    fiscal_year_end: str  # MM-DD


def load_clubs(path: Path = CONFIG_DIR / "clubs.yaml") -> list[Club]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Club(**club) for club in data["clubs"]]


def fiscal_year_end_date(season: str, fiscal_year_end: str) -> date:
    """Cierre del año fiscal de una temporada: ("2024/25", "05-31") -> 2025-05-31."""
    match = re.fullmatch(r"(\d{4})/(\d{2})", season)
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise ValueError(f"Temporada no válida: {season!r}. Formato esperado: 2024/25")
    month, day = (int(part) for part in fiscal_year_end.split("-"))
    return date(int(match[1]) + 1, month, day)


def season_slug(season: str) -> str:
    """Temporada para nombres de archivo: "2024/25" -> "2024_25"."""
    return season.replace("/", "_")
