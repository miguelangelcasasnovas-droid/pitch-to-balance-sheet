"""Reparto de los ingresos en matchday, broadcasting, commercial y other (fase 3a).

Lee config/line_items.yaml: cada partida original de ingresos de cada club, la celda de la
especificación que la lee y el concepto al que va, con el motivo. De ahí salen:
- las cifras de los cuatro conceptos: la suma de sus partidas, cada una con su fuente;
- los huecos: un concepto al que podría ir una partida dudosa (sin concepto hasta que decida el
  usuario), o al que no va ninguna partida;
- el cuadre de que todas las partidas, traspasos incluidos, suman el total publicado. Una fila
  de ingresos sin partida hace que no cuadre: rompe la build.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from pitch_to_balance_sheet.config import CONFIG_DIR
from pitch_to_balance_sheet.extract.statements import FigureSpec, LinkSum, Part

MIX = ("revenue_matchday", "revenue_broadcasting", "revenue_commercial", "revenue_other")
PLAYER_TRADING = "player_trading"  # traspasos o cesiones dentro de los ingresos: se restan
UNASSIGNED = "_revenue_unassigned"  # partidas sin concepto firme; interna, no va al CSV
LINE_ITEMS = CONFIG_DIR / "line_items.yaml"


@dataclass(frozen=True)
class LineItem:
    key: str
    table: str
    row: str
    column: str
    label: str  # la partida tal como la llama el informe
    concept: str | None  # None: dudosa, hasta que decida el usuario
    reason: str
    candidates: tuple[str, ...] = ()  # conceptos posibles de una partida dudosa

    @property
    def cell(self) -> tuple[str, str, str]:
        return (self.table, self.row, self.column)


@dataclass(frozen=True)
class ClubMix:
    club_id: str
    source: str
    total: tuple[str, str, str]  # celda del total publicado que suman las partidas
    items: tuple[LineItem, ...]

    def _pending(self) -> dict[str, list[LineItem]]:
        pending: dict[str, list[LineItem]] = {}
        for item in self.items:
            for concept in item.candidates:
                pending.setdefault(concept, []).append(item)
        return pending

    def gaps(self) -> dict[str, str]:
        """Conceptos sin cifra: a los que podría ir una dudosa, o a los que no va ninguna."""
        pending, gaps = self._pending(), {}
        for concept in MIX:
            if concept in pending:
                gaps[concept] = "pendiente de decidir: " + "; ".join(
                    f"la partida dudosa «{item.label}» puede ir a "
                    + " o ".join(item.candidates) for item in pending[concept]
                ) + f" ({self.source})"
            elif not any(item.concept == concept for item in self.items):
                gaps[concept] = (f"el club no tiene una partida de este tipo: sus partidas "
                                 f"({self.source}) suman el total sin ella")
        return gaps

    def figures(self, column: str) -> tuple[FigureSpec, ...]:
        """Cifras de los conceptos firmes y, aparte, la suma de las partidas sin concepto firme,
        que solo sirve para la validación."""
        gaps, figures, unassigned = self.gaps(), [], []
        for concept in MIX:
            items = [item for item in self.items if item.concept == concept]
            if concept in gaps:
                unassigned += items
                continue
            figures.append(FigureSpec(
                concept, tuple(Part(item.table, item.row, item.column) for item in items),
                column, note=f"{' + '.join(item.label for item in items)} ({self.source}). "
                             "Mapeo en config/line_items.yaml."))
        unassigned += [item for item in self.items if item.concept is None]
        if unassigned:
            figures.append(FigureSpec(
                UNASSIGNED, tuple(Part(item.table, item.row, item.column) for item in unassigned),
                column))
        return tuple(figures)

    def check(self) -> LinkSum:
        """El total publicado es la suma de todas las partidas, traspasos incluidos."""
        return LinkSum(self.total, tuple(item.cell for item in self.items))

    @property
    def lines(self) -> int:
        """Partidas que suman revenue_ex_player_trading (sin las de traspasos)."""
        return sum(item.concept != PLAYER_TRADING for item in self.items)


def _cell(text: str, column: str) -> tuple[str, str, str]:
    """"tabla.fila" en la columna del club, o "tabla.fila.columna"."""
    parts = text.split(".")
    return (parts[0], parts[1], parts[2] if len(parts) == 3 else column)


def load(season: str = "2024/25", path: Path = LINE_ITEMS) -> dict[str, ClubMix]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if season not in data:
        raise ValueError(f"no hay partidas de ingresos para {season} en {path.name}")
    clubs = {}
    for club_id, club in data[season].items():
        items = []
        for key, item in club["items"].items():
            concept = item.get("concept")
            candidates = tuple(item.get("candidates", ()))
            if concept is None:
                if len(candidates) < 2 or not set(candidates) <= set(MIX):
                    raise ValueError(f"{club_id}.{key}: una partida dudosa necesita dos o más "
                                     f"candidatos de {MIX}")
            elif concept not in (*MIX, PLAYER_TRADING) or candidates:
                raise ValueError(f"{club_id}.{key}: concepto {concept!r} no previsto")
            if not item.get("reason"):
                raise ValueError(f"{club_id}.{key}: falta el motivo")
            column = item.get("column", club["column"])
            items.append(LineItem(key, *_cell(item["cell"], column)[:2], column, item["label"],
                                  concept, item["reason"], candidates))
        clubs[club_id] = ClubMix(club_id, club["source"], _cell(club["total"], club["column"]),
                                 tuple(items))
    return clubs


def for_club(club_id: str, season: str = "2024/25") -> ClubMix:
    clubs = load(season)
    if club_id not in clubs:
        raise ValueError(f"{club_id} no tiene sus partidas de ingresos en {LINE_ITEMS.name}")
    return clubs[club_id]
