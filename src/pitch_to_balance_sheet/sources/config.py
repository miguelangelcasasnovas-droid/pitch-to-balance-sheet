"""config/sources.yaml: de qué documento sale cada club en cada temporada."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from pitch_to_balance_sheet.config import CONFIG_DIR

KINDS = ("companies_house", "url", "manual")


@dataclass(frozen=True)
class Source:
    kind: str
    url: str | None = None
    file: str | None = None  # ruta relativa a data/raw/, en las manuales y las de la web
    note: str | None = None


@dataclass(frozen=True)
class ClubSources:
    club_id: str
    primary: Source
    controls: tuple[Source, ...] = ()

    @property
    def all(self) -> tuple[Source, ...]:
        return (self.primary, *self.controls)


def _source(club_id: str, data: dict) -> Source:
    source = Source(**data)
    if source.kind not in KINDS:
        raise ValueError(f"{club_id}: tipo de fuente desconocido {source.kind!r}")
    if source.kind in ("url", "manual") and not source.url:
        raise ValueError(f"{club_id}: la fuente {source.kind} necesita url")
    if source.kind in ("url", "manual") and not source.file:
        raise ValueError(f"{club_id}: la fuente {source.kind} necesita file")
    return source


def load_sources(season: str, path: Path = CONFIG_DIR / "sources.yaml") -> dict[str, ClubSources]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if season not in data:
        raise ValueError(f"No hay fuentes para la temporada {season} en {path.name}")
    return {
        club_id: ClubSources(
            club_id=club_id,
            primary=_source(club_id, club["primary"]),
            controls=tuple(_source(club_id, control) for control in club.get("controls", [])),
        )
        for club_id, club in data[season].items()
    }
