"""Tipos de cambio de referencia del BCE y conversión a EUR (sección 5 del plan).

La serie diaria EXR.D.<moneda>.EUR.SP00.A da unidades de la moneda por 1 EUR (p. ej. 0,8555 GBP
el 30/06/2025), así que el importe en EUR es el importe en la moneda dividido entre el tipo.

- Cuenta de resultados: la media aritmética de los tipos diarios publicados en el año fiscal
  del club, redondeada a 6 decimales.
- Balance: el tipo del día de cierre o, si ese día el BCE no publica (fin de semana o festivo
  TARGET), el del último día anterior con tipo.
- value_eur = importe en unidades de la moneda / fx_rate, redondeado al euro (mitad hacia
  arriba). Así fx_rate y value_eur se pueden comprobar en la propia tabla.

Un tipo que falta es un error: no se rellena ni se interpola.
"""

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pitch_to_balance_sheet.config import fiscal_year_end_date, season_slug

BASE = "EUR"
RATE_DECIMALS = Decimal("0.000001")  # precisión de la media
# Días naturales sin tipo que se admiten: un fin de semana largo con festivos TARGET (Viernes
# Santo y Lunes de Pascua) deja 4 días seguidos sin tipo.
MAX_GAP_DAYS = 5
URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
       "?startPeriod={start}&endPeriod={end}&format=csvdata")

# Cómo se convierte cada fila de fact_financials.
AVERAGE = "average_fiscal_year"  # cuenta de resultados
CLOSING = "closing"  # balance
NO_CONVERSION = "none_eur"  # la cifra ya está en EUR
NOT_MONETARY = "not_monetary"  # p. ej. número de acciones


class FxError(RuntimeError):
    """Falta el archivo de tipos, no es la serie esperada o no cubre las fechas."""


@dataclass(frozen=True)
class Rate:
    rate: Decimal  # unidades de la moneda por 1 EUR
    method: str
    date: str  # el día del tipo de cierre, o el año fiscal "2024-07-01/2025-06-30" de la media
    observations: int  # tipos diarios usados
    note: str


def series_key(currency: str) -> str:
    return f"EXR.D.{currency}.EUR.SP00.A"


def rates_file(currency: str, season: str) -> str:
    """Ruta en data/raw/ del archivo de tipos de una moneda y temporada."""
    return f"ecb/exr_d_{currency.lower()}_eur_{season_slug(season)}.csv"


def fiscal_year(season: str, fiscal_year_end: str) -> tuple[date, date]:
    """Primer y último día del año fiscal: del día siguiente al cierre anterior al cierre."""
    end = fiscal_year_end_date(season, fiscal_year_end)
    return end.replace(year=end.year - 1) + timedelta(days=1), end


def download_url(currency: str, start: date, end: date) -> str:
    return URL.format(currency=currency, start=start.isoformat(), end=end.isoformat())


def load_rates(path: Path, currency: str) -> dict[date, Decimal]:
    """Los tipos diarios del CSV del BCE (format=csvdata), por fecha."""
    if not path.exists():
        raise FxError(f"falta {path}: ejecuta download-fx")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"KEY", "TIME_PERIOD", "OBS_VALUE"} - set(reader.fieldnames or ())
        if missing:
            raise FxError(f"{path.name} no es un CSV del BCE: faltan {', '.join(sorted(missing))}")
        rates = {}
        for row in reader:
            if row["KEY"] != series_key(currency):
                raise FxError(f"{path.name}: serie {row['KEY']}, se esperaba "
                              f"{series_key(currency)}")
            if not row["OBS_VALUE"]:
                raise FxError(f"{path.name}: el {row['TIME_PERIOD']} no tiene tipo")
            day = date.fromisoformat(row["TIME_PERIOD"])
            if day in rates:
                raise FxError(f"{path.name}: el {day} aparece dos veces")
            rates[day] = Decimal(row["OBS_VALUE"])
    if not rates:
        raise FxError(f"{path.name} no tiene tipos")
    return rates


def _check_gaps(days: list[date], start: date, end: date, what: str) -> None:
    """Que los tipos cubren el periodo: ningún tramo sin tipo de más de MAX_GAP_DAYS días."""
    edges = [start - timedelta(days=1), *days, end + timedelta(days=1)]
    for before, after in zip(edges, edges[1:], strict=False):
        if (after - before).days - 1 > MAX_GAP_DAYS:
            raise FxError(f"{what}: no hay tipos entre el {before + timedelta(days=1)} y el "
                          f"{after - timedelta(days=1)} (más de {MAX_GAP_DAYS} días seguidos)")


def average_rate(rates: dict[date, Decimal], currency: str, start: date, end: date) -> Rate:
    days = sorted(day for day in rates if start <= day <= end)
    _check_gaps(days, start, end, f"media {currency} del {start} al {end}")
    mean = sum(rates[day] for day in days) / len(days)
    return Rate(mean.quantize(RATE_DECIMALS, rounding=ROUND_HALF_UP), AVERAGE,
                f"{start.isoformat()}/{end.isoformat()}", len(days),
                f"media de {len(days)} tipos diarios del BCE ({series_key(currency)}) del "
                f"{start:%d/%m/%Y} al {end:%d/%m/%Y}, redondeada a 6 decimales")


def closing_rate(rates: dict[date, Decimal], currency: str, day: date) -> Rate:
    previous = [d for d in rates if d <= day and (day - d).days <= MAX_GAP_DAYS]
    if not previous:
        raise FxError(f"cierre {currency} del {day}: no hay tipo ese día ni en los "
                      f"{MAX_GAP_DAYS} anteriores")
    used = max(previous)
    why = "del día de cierre" if used == day else (
        f"del {used:%d/%m/%Y}, último día con tipo antes del cierre ({day:%d/%m/%Y})")
    return Rate(rates[used], CLOSING, used.isoformat(), 1,
                f"tipo de referencia del BCE ({series_key(currency)}) {why}")


def to_eur(value_full: int | Decimal, rate: Decimal) -> int:
    """Unidades de la moneda / tipo, redondeado al euro (mitad hacia arriba)."""
    return int((Decimal(value_full) / rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))
