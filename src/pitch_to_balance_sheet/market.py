"""Precios de mercado de los cotizados a la fecha de valoración (plan, sección 9).

No se descargan: el robots.txt de las APIs de Yahoo prohíbe la descarga automática y el plan
(sección 2) pide entonces descarga manual documentada (decisión del usuario del 29/09/2026). El
cierre de cada ticker se toma a mano de la web de su bolsa y se escribe en el CSV de
config/market.yaml (data/raw/manual/prices_<fecha>.csv), con una fila por ticker y las columnas
de COLUMNS; después se registra en el manifiesto con register-manual.

Cada fila tiene que:
- ser de un ticker de config/clubs.yaml, y estar todos;
- traer el cierre del día de valoración o del último día de cotización anterior, como mucho
  MAX_STALE_DAYS días antes;
- venir en la unidad de cotización de config/clubs.yaml (GBp son peniques) y con su moneda ISO;
- llevar su fuente: source_url (http o https), source_name y retrieved_at (fecha ISO).
Si falta el archivo o una fila no cumple, es un error que dice qué falta y de dónde sacarlo.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from pitch_to_balance_sheet.config import CONFIG_DIR, ROOT, Club

COLUMNS = ["ticker", "date", "close", "currency", "unit", "source_url", "source_name",
           "retrieved_at", "note"]
REQUIRED = [column for column in COLUMNS if column != "note"]
MAX_STALE_DAYS = 5  # un cierre más antiguo que esto es un error
MARKET_CONFIG = CONFIG_DIR / "market.yaml"


class MarketError(RuntimeError):
    """Falta el archivo de precios o un precio no es el esperado."""


@dataclass(frozen=True)
class MarketConfig:
    season: str
    valuation_date: date
    prices_file: str  # ruta en data/raw/
    template: str  # ruta desde la raíz del proyecto
    illiquid: dict[str, str]  # ticker -> motivo


@dataclass(frozen=True)
class Price:
    ticker: str
    date: date
    close: Decimal  # en la unidad de cotización (peniques en GBp)
    currency: str  # moneda ISO
    unit: str  # unidad de cotización: GBp, GBP, USD, EUR
    source_url: str
    source_name: str
    retrieved_at: str
    note: str  # la de la fila y, si toca, el cierre anterior o la iliquidez
    illiquid: str = ""  # motivo, si el valor no se negoció ese día


def load_config(season: str, path: Path = MARKET_CONFIG) -> MarketConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if season not in data:
        raise MarketError(f"no hay precios de mercado para {season} en {path.name}")
    entry = data[season]
    return MarketConfig(season, date.fromisoformat(entry["valuation_date"]),
                        entry["prices_file"], entry["template"],
                        dict(entry.get("illiquid") or {}))


def iso_currency(unit: str) -> str:
    """La moneda ISO de una unidad de cotización: GBp (peniques) es GBP."""
    return "GBP" if unit == "GBp" else unit


def where_to_find(clubs: list[Club], config: MarketConfig) -> str:
    """De dónde sacar el precio de cada cotizado."""
    return "\n".join(
        f"- {club.ticker} ({club.name}): cierre del {config.valuation_date:%d/%m/%Y} (o del último "
        f"día de cotización anterior) en {club.exchange}, en {club.quote_currency}"
        + (" (peniques)" if club.quote_currency == "GBp" else "")
        for club in clubs if club.ticker)


def missing_file_message(path: Path, clubs: list[Club], config: MarketConfig) -> str:
    return (f"falta {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}. Copia la "
            f"plantilla {config.template}, rellena una fila por ticker con su fuente "
            f"(source_url, source_name, retrieved_at) y regístrala con register-manual. Precios:"
            f"\n{where_to_find(clubs, config)}")


def load_prices(path: Path, clubs: list[Club], config: MarketConfig) -> dict[str, Price]:
    """Los precios del CSV manual, comprobados, por club_id."""
    if not path.exists():
        raise MarketError(missing_file_message(path, clubs, config))
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise MarketError(f"{path.name}: las columnas tienen que ser {', '.join(COLUMNS)}; "
                              f"son {', '.join(reader.fieldnames or [])}")
        rows = list(reader)
    listed = {club.ticker: club for club in clubs if club.ticker}
    tickers = [row["ticker"] for row in rows]
    unknown = sorted(set(tickers) - set(listed))
    repeated = sorted({t for t in tickers if tickers.count(t) > 1})
    absent = sorted(set(listed) - set(tickers))
    if unknown or repeated or absent:
        raise MarketError(f"{path.name}: " + "; ".join(
            text for text in (f"tickers que no están en config/clubs.yaml: {', '.join(unknown)}"
                              if unknown else "",
                              f"tickers repetidos: {', '.join(repeated)}" if repeated else "",
                              f"faltan: {', '.join(absent)}" if absent else "") if text))
    prices, problems = {}, []
    for row in rows:
        club = listed[row["ticker"]]
        try:
            prices[club.club_id] = _price(row, club, config)
        except MarketError as exc:
            problems.append(f"{row['ticker']}: {exc}")
    if problems:
        raise MarketError(f"{path.name}:\n" + "\n".join(f"- {p}" for p in problems)
                          + f"\nDe dónde sacar cada precio:\n{where_to_find(clubs, config)}")
    return prices


def _price(row: dict, club: Club, config: MarketConfig) -> Price:
    empty = [column for column in REQUIRED if not (row.get(column) or "").strip()]
    if empty:
        raise MarketError(f"sin rellenar: {', '.join(empty)}")
    try:
        day = date.fromisoformat(row["date"].strip())
        close = Decimal(row["close"].strip())
        datetime.fromisoformat(row["retrieved_at"].strip())
    except (ValueError, InvalidOperation) as exc:
        raise MarketError(f"fecha, cierre o retrieved_at no válidos ({exc})") from exc
    if close <= 0:
        raise MarketError(f"el cierre tiene que ser positivo, y es {close}")
    if day > config.valuation_date:
        raise MarketError(f"el cierre es del {day}, después de la fecha de valoración")
    if (config.valuation_date - day).days > MAX_STALE_DAYS:
        raise MarketError(f"el cierre es del {day}, más de {MAX_STALE_DAYS} días antes del "
                          f"{config.valuation_date}")
    unit, currency = row["unit"].strip(), row["currency"].strip()
    if unit != club.quote_currency:
        raise MarketError(f"la unidad es {unit} y {club.ticker} cotiza en {club.quote_currency}")
    if currency != iso_currency(unit):
        raise MarketError(f"la moneda de {unit} es {iso_currency(unit)}, no {currency}")
    if not row["source_url"].strip().startswith(("http://", "https://")):
        raise MarketError("source_url tiene que ser una URL http o https")
    notes = [row["note"].strip()] if (row.get("note") or "").strip() else []
    if day != config.valuation_date:
        notes.append(f"cierre del {day:%d/%m/%Y}, último día de cotización antes del "
                     f"{config.valuation_date:%d/%m/%Y}")
    illiquid = config.illiquid.get(club.ticker, "")
    if illiquid:
        notes.append(f"ilíquido: {illiquid}")
    return Price(club.ticker, day, close, currency, unit, row["source_url"].strip(),
                 row["source_name"].strip(), row["retrieved_at"].strip(), "; ".join(notes),
                 illiquid)


def write_template(path: Path, clubs: list[Club]) -> None:
    """La plantilla: una fila por ticker, con el resto de columnas vacías."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for club in clubs:
            if club.ticker:
                writer.writerow({"ticker": club.ticker})
