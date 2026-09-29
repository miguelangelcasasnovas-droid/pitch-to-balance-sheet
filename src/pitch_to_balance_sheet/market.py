"""Precios de mercado de los cotizados con yfinance (plan, secciones 6 y 9), a la fecha de
valoración.

- Se descarga el histórico diario de una ventana de días hasta la fecha de valoración y se guarda
  tal cual en data/raw/market/<ticker>_<fecha>.csv, con su entrada en el manifiesto. La URL del
  manifiesto es la del endpoint que consulta yfinance 1.7.0 (chart de query2.finance.yahoo.com).
- El precio es el cierre sin ajustar (Close, no Adj Close) del día de valoración o del último día
  de cotización anterior, como mucho MAX_STALE_DAYS días antes. Yahoo da los precios en coma
  flotante (17.809999465942383): se guardan también redondeados a 4 decimales, que es la
  precisión con la que cotizan estos valores.
- La moneda de cotización que devuelve yfinance tiene que ser la de config/clubs.yaml
  (quote_currency); si no, error. GBp son peniques: quote_divisor pasa a libras.

El robots.txt de query1 y query2.finance.yahoo.com dice «Disallow: /». El uso de yfinance es una
decisión del usuario (plan, secciones 4, 6 y 11); la alternativa es descargar los precios a mano
de la web de cada bolsa.
"""

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pitch_to_balance_sheet.config import Club
from pitch_to_balance_sheet.manifest import ManifestEntry, sha256_bytes

VALUATION_DATE = date(2025, 6, 30)  # plan, sección 9, supuesto 1
WINDOW_DAYS = 14  # días naturales de histórico antes de la fecha de valoración
MAX_STALE_DAYS = 5  # un cierre más antiguo que esto es un error
PRICE_DECIMALS = Decimal("0.0001")
FIELDS = ["ticker", "date", "open", "high", "low", "close", "close_raw", "adj_close", "volume",
          "currency", "exchange", "timezone"]
CHART_URL = ("https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}"
             "&period2={end}&interval=1d")


class MarketError(RuntimeError):
    """El precio no se puede descargar o no es el esperado."""


@dataclass(frozen=True)
class Price:
    ticker: str
    date: date
    close: Decimal  # en la moneda de cotización (peniques en GBp)
    currency: str
    volume: int
    source_file: str
    note: str


def iso_currency(quote_currency: str) -> str:
    """La moneda ISO de una cotización: GBp (peniques) es GBP."""
    return "GBP" if quote_currency == "GBp" else quote_currency


def price_file(ticker: str, valuation_date: date = VALUATION_DATE) -> str:
    """Ruta en data/raw/ del histórico de un ticker."""
    return f"market/{ticker.lower()}_{valuation_date.isoformat()}.csv"


def _epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def _round(value: float) -> str:
    return str(Decimal(repr(float(value))).quantize(PRICE_DECIMALS, rounding=ROUND_HALF_UP))


def download_price(club: Club, raw_dir: Path, valuation_date: date = VALUATION_DATE,
                   ticker_factory=None) -> ManifestEntry:
    """Descarga con yfinance el histórico de la ventana y lo guarda con su entrada del
    manifiesto. ticker_factory sustituye a yfinance.Ticker en los tests."""
    if ticker_factory is None:
        import yfinance

        yfinance.set_tz_cache_location(str(Path(".cache") / "yfinance"))
        ticker_factory = yfinance.Ticker
    start, end = valuation_date - timedelta(days=WINDOW_DAYS), valuation_date + timedelta(days=1)
    ticker = ticker_factory(club.ticker)
    history = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False,
                             actions=False)
    if history is None or history.empty:
        raise MarketError(f"{club.ticker}: yfinance no devuelve cotizaciones del {start} al "
                          f"{valuation_date}")
    metadata = ticker.history_metadata or {}
    currency = metadata.get("currency")
    if currency != club.quote_currency:
        raise MarketError(f"{club.ticker}: yfinance da la moneda {currency!r} y config/clubs.yaml "
                          f"espera {club.quote_currency!r}")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for stamp, row in history.iterrows():
        writer.writerow({
            "ticker": club.ticker, "date": stamp.date().isoformat(),
            "open": _round(row["Open"]), "high": _round(row["High"]), "low": _round(row["Low"]),
            "close": _round(row["Close"]), "close_raw": repr(float(row["Close"])),
            "adj_close": _round(row["Adj Close"]), "volume": int(row["Volume"]),
            "currency": currency, "exchange": metadata.get("exchangeName", ""),
            "timezone": metadata.get("exchangeTimezoneName", ""),
        })
    content = buffer.getvalue().encode("utf-8")
    file = price_file(club.ticker, valuation_date)
    path = raw_dir / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return ManifestEntry(
        file=file,
        url=CHART_URL.format(ticker=club.ticker, start=_epoch(start), end=_epoch(end)),
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        sha256=sha256_bytes(content),
        bytes=len(content),
        content_type="text/csv",
    )


def load_price(path: Path, club: Club, valuation_date: date = VALUATION_DATE) -> Price:
    """El cierre del día de valoración o del último día de cotización anterior."""
    if not path.exists():
        raise MarketError(f"falta {path}: ejecuta download-prices")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    wrong = {row["ticker"] for row in rows} - {club.ticker}
    if wrong or {row["currency"] for row in rows} - {club.quote_currency}:
        raise MarketError(f"{path.name} no es de {club.ticker} en {club.quote_currency}")
    before = [row for row in rows if date.fromisoformat(row["date"]) <= valuation_date]
    if not before:
        raise MarketError(f"{path.name}: no hay cotización el {valuation_date} ni antes")
    row = max(before, key=lambda r: r["date"])
    day = date.fromisoformat(row["date"])
    if (valuation_date - day).days > MAX_STALE_DAYS:
        raise MarketError(f"{club.ticker}: la última cotización es del {day}, más de "
                          f"{MAX_STALE_DAYS} días antes del {valuation_date}")
    note = ("cierre del día de valoración" if day == valuation_date
            else f"cierre del {day:%d/%m/%Y}, último día de cotización antes del "
                 f"{valuation_date:%d/%m/%Y}")
    if int(row["volume"]) == 0:
        note += "; ese día no hubo negociación (volumen 0) y Yahoo da el último cierre"
    return Price(club.ticker, day, Decimal(row["close"]), row["currency"], int(row["volume"]),
                 path.name, note)
