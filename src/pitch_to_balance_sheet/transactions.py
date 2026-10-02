"""Transacciones precedentes (plan, sección 9; decisión del usuario del 02/10/2026).

Cada operación de config/transactions.yaml tiene un precio, tal como lo publica su fuente, y un
ejercicio de referencia: el último cuyas cuentas ya estaban publicadas el día del anuncio. De
esas cuentas salen revenue_ex_player_trading y net_debt (borrowings − cash) con las reglas de
siempre (extractor de src/pitch_to_balance_sheet/extract/references/).

- equity: el importe es el valor del equity al 100 %; EV = equity + net_debt.
- ev: el importe es el valor de empresa; equity implícito = EV − net_debt.
- per_share: precio por acción × shares_outstanding del informe de referencia; EV = equity +
  net_debt.
- Múltiplo = EV / revenue_ex_player_trading, en la moneda de las cuentas, sin pasar a EUR. Si
  el precio va en otra moneda (Manchester United: USD, cuentas en GBP), el precio se pasa a la
  moneda de las cuentas con los tipos del BCE del día del anuncio o del último día anterior con
  tipo: es la única conversión.
- tier: base (fuente primaria del precio), press_only (solo prensa: sensibilidad, marcada en
  todas las salidas) o excluded (fuera, con su motivo).
"""

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import yaml

from pitch_to_balance_sheet import fx
from pitch_to_balance_sheet.config import CONFIG_DIR, Club, fiscal_year_end_date, load_clubs

TRANSACTIONS_CONFIG = CONFIG_DIR / "transactions.yaml"
TIERS = ("base", "press_only", "excluded")
BASES = ("equity", "ev", "per_share")
PRESS_ONLY_MARK = "solo prensa (sin fuente primaria del precio)"
FX_WINDOW_DAYS = 10  # días antes del anuncio que se bajan del BCE
OK, EXCLUDED, PENDING = "ok", "excluded", "pending"


class TransactionsError(RuntimeError):
    """La configuración de las operaciones no es válida o falta un dato para calcularlas."""


@dataclass(frozen=True)
class Variant:
    variant: str
    basis: str
    amount: Decimal | None = None  # en unidades de price_currency
    price_per_share: Decimal | None = None


@dataclass(frozen=True)
class Reference:
    season: str
    published: date
    evidence: str


@dataclass(frozen=True)
class Deal:
    deal_id: str
    name: str
    tier: str
    announced: date
    price_currency: str
    price_primary: bool
    price_source: str
    price_text: str
    variants: tuple[Variant, ...] = ()
    club_id: str = ""
    closed: date | None = None
    buyer: str = ""
    stake: str = ""
    note: str = ""
    reason: str = ""
    reference: Reference | None = None


def _decimal(value, what: str) -> Decimal:
    try:
        return Decimal(str(value))
    except ArithmeticError as exc:
        raise TransactionsError(f"{what}: {value!r} no es un número") from exc


def _variant(deal_id: str, data: dict) -> Variant:
    basis = data.get("basis")
    if basis not in BASES:
        raise TransactionsError(f"{deal_id}: basis {basis!r} no válida; se espera "
                                f"{', '.join(BASES)}")
    amount = data.get("amount")
    per_share = data.get("price_per_share")
    if basis == "per_share" and (per_share is None or amount is not None):
        raise TransactionsError(f"{deal_id}: una variante per_share lleva price_per_share y no "
                                "amount")
    if basis != "per_share" and (amount is None or per_share is not None):
        raise TransactionsError(f"{deal_id}: una variante {basis} lleva amount y no "
                                "price_per_share")
    variant = Variant(data["variant"], basis,
                      _decimal(amount, f"{deal_id} amount") if amount is not None else None,
                      _decimal(per_share, f"{deal_id} price_per_share")
                      if per_share is not None else None)
    if (variant.amount or variant.price_per_share) <= 0:
        raise TransactionsError(f"{deal_id}: el precio tiene que ser positivo")
    return variant


def _deal(data: dict) -> Deal:
    deal_id = data["deal_id"]
    tier = data.get("tier")
    if tier not in TIERS:
        raise TransactionsError(f"{deal_id}: tier {tier!r} no válido; se espera "
                                f"{', '.join(TIERS)}")
    announced = date.fromisoformat(data["announced"])
    variants = tuple(_variant(deal_id, v) for v in data.get("variants") or ())
    names = [v.variant for v in variants]
    if len(set(names)) != len(names):
        raise TransactionsError(f"{deal_id}: variantes repetidas")
    reference = None
    if tier == "excluded":
        if not (data.get("reason") or "").strip():
            raise TransactionsError(f"{deal_id}: una operación excluida lleva su motivo (reason)")
        if variants:
            raise TransactionsError(f"{deal_id}: una operación excluida no lleva variantes")
    else:
        if not variants or not data.get("club_id") or not data.get("reference"):
            raise TransactionsError(f"{deal_id}: una operación {tier} lleva club_id, variants y "
                                    "reference")
        if tier == "base" and not data.get("price_primary"):
            raise TransactionsError(f"{deal_id}: una operación base tiene que tener fuente "
                                    "primaria del precio")
        if tier == "press_only" and data.get("price_primary"):
            raise TransactionsError(f"{deal_id}: con fuente primaria no es press_only")
        ref = data["reference"]
        reference = Reference(ref["season"], date.fromisoformat(ref["published"]),
                              " ".join(str(ref["evidence"]).split()))
        if reference.published > announced:
            raise TransactionsError(
                f"{deal_id}: las cuentas de {reference.season} se publicaron el "
                f"{reference.published}, después del anuncio ({announced}): no pueden ser el "
                "ejercicio de referencia")
    return Deal(
        deal_id=deal_id, name=data["name"], tier=tier, announced=announced,
        price_currency=data["price_currency"], price_primary=bool(data.get("price_primary")),
        price_source=data["price_source"], price_text=" ".join(str(data["price_text"]).split()),
        variants=variants, club_id=data.get("club_id", ""),
        closed=date.fromisoformat(data["closed"]) if data.get("closed") else None,
        buyer=data.get("buyer", ""), stake=data.get("stake", ""),
        note=" ".join(str(data.get("note", "")).split()),
        reason=" ".join(str(data.get("reason", "")).split()), reference=reference)


def load_deals(path: Path = TRANSACTIONS_CONFIG) -> list[Deal]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    deals = [_deal(item) for item in data["deals"]]
    ids = [deal.deal_id for deal in deals]
    if len(set(ids)) != len(ids):
        raise TransactionsError("deal_id repetidos en " + path.name)
    return deals


def load_targets(path: Path = TRANSACTIONS_CONFIG) -> list[Club]:
    """Los clubes de las operaciones que no están en config/clubs.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Club(**club) for club in data.get("targets") or ()]


def all_clubs(path: Path = TRANSACTIONS_CONFIG) -> dict[str, Club]:
    clubs = {club.club_id: club for club in load_clubs()}
    for club in load_targets(path):
        if club.club_id in clubs:
            raise TransactionsError(f"{club.club_id} ya está en config/clubs.yaml: quítalo de "
                                    "targets")
        clubs[club.club_id] = club
    return clubs


def period_end(deal: Deal, club: Club, made_up_date: str | None = None) -> date:
    """Cierre de las cuentas de referencia: el de la fuente si lo da, o el de la temporada."""
    if made_up_date:
        return date.fromisoformat(made_up_date)
    return fiscal_year_end_date(deal.reference.season, club.fiscal_year_end)


def rates_file(currency: str, deal: Deal) -> str:
    """Tipos del BCE de los días anteriores al anuncio de una operación, en data/raw/."""
    return f"ecb/exr_d_{currency.lower()}_eur_{deal.deal_id}.csv"


def rates_window(deal: Deal) -> tuple[date, date]:
    return deal.announced - timedelta(days=FX_WINDOW_DAYS), deal.announced


@dataclass(frozen=True)
class Financials:
    """Las cifras del ejercicio de referencia, en unidades de la moneda de las cuentas."""

    currency: str
    period_end: date
    revenue_ex_player_trading: int
    borrowings: int
    cash: int
    shares_outstanding: int | None = None
    # Préstamos de vinculadas sin interés ni calendario: informativo, no entra en net_debt.
    related_party_financing: int | None = None
    source_file: str = ""
    sha256: str = ""
    sources: str = ""  # página y fila de cada cifra
    note: str = ""

    @property
    def net_debt(self) -> int:
        return self.borrowings - self.cash


@dataclass(frozen=True)
class CrossRate:
    """Unidades de la moneda de las cuentas por unidad de la moneda del precio."""

    rate: Decimal
    date: str
    note: str


def cross_rate(price: dict[date, Decimal] | None, accounts: dict[date, Decimal] | None,
               price_currency: str, accounts_currency: str, day: date) -> CrossRate:
    """Tipo cruzado con los tipos del BCE (moneda por EUR) del día del anuncio o del último día
    anterior con tipo."""
    parts, quoted, days = [], [], []
    for currency, rates in ((price_currency, price), (accounts_currency, accounts)):
        if currency == fx.BASE:
            parts.append(Decimal(1))
            continue
        if rates is None:
            raise TransactionsError(f"faltan los tipos del BCE de {currency}")
        rate = fx.closing_rate(rates, currency, day)
        parts.append(rate.rate)
        quoted.append(f"{currency} {rate.rate}")
        days.append(rate.date)
    used = sorted(set(days))
    when = ", ".join(date.fromisoformat(d).strftime("%d/%m/%Y") for d in used)
    why = ("el día del anuncio" if used == [day.isoformat()] else
           f"último día con tipo antes del anuncio del {day:%d/%m/%Y}")
    return CrossRate(parts[1] / parts[0], ", ".join(used),
                     f"tipos de referencia del BCE del {when} ({why}): {' y '.join(quoted)} por "
                     f"EUR; {accounts_currency} por {price_currency} = {parts[1]} / {parts[0]}")


def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass
class Row:
    deal_id: str
    name: str
    tier: str
    variant: str
    basis: str
    status: str
    club_id: str = ""
    announced: str = ""
    closed: str = ""
    buyer: str = ""
    stake: str = ""
    price_currency: str = ""
    price_primary: bool = False
    price_source: str = ""
    price_text: str = ""
    price_per_share: float | None = None
    price_amount: int | None = None  # en price_currency: amount, o precio × acciones
    shares_outstanding: int | None = None
    reference_season: str = ""
    reference_period_end: str = ""
    reference_published: str = ""
    reference_evidence: str = ""
    currency: str = ""  # la de las cuentas: la de equity, EV, deuda e ingresos
    fx_rate: float | None = None
    fx_date: str = ""
    fx_note: str = ""
    equity_value: int | None = None
    borrowings: int | None = None
    cash: int | None = None
    net_debt: int | None = None
    related_party_financing: int | None = None  # informativo: no entra en net_debt ni en el EV
    ev: int | None = None
    revenue_ex_player_trading: int | None = None
    ev_to_revenue: float | None = None
    source_file: str = ""
    sha256: str = ""
    sources: str = ""
    reason: str = ""
    note: str = ""
    marks: list[str] = field(default_factory=list)


def _base_row(deal: Deal, variant: Variant | None) -> Row:
    marks = [PRESS_ONLY_MARK] if deal.tier == "press_only" else []
    return Row(
        deal_id=deal.deal_id, name=deal.name, tier=deal.tier,
        variant=variant.variant if variant else "", basis=variant.basis if variant else "",
        status=OK, club_id=deal.club_id, announced=deal.announced.isoformat(),
        closed=deal.closed.isoformat() if deal.closed else "", buyer=deal.buyer,
        stake=deal.stake, price_currency=deal.price_currency, price_primary=deal.price_primary,
        price_source=deal.price_source, price_text=deal.price_text,
        price_per_share=float(variant.price_per_share) if variant and variant.price_per_share
        else None,
        reference_season=deal.reference.season if deal.reference else "",
        reference_published=deal.reference.published.isoformat() if deal.reference else "",
        reference_evidence=deal.reference.evidence if deal.reference else "",
        reason=deal.reason, note=deal.note, marks=marks)


def compute(deals: list[Deal], financials: dict[str, Financials],
            rates: dict[str, CrossRate] | None = None,
            pending: dict[str, str] | None = None) -> list[Row]:
    """Una fila por operación y variante. financials y rates van por deal_id; pending, el motivo
    de las operaciones cuyas cuentas no se han podido leer."""
    rates, pending = rates or {}, pending or {}
    rows = []
    for deal in deals:
        if deal.tier == "excluded":
            row = _base_row(deal, None)
            row.status = EXCLUDED
            rows.append(row)
            continue
        for variant in deal.variants:
            row = _base_row(deal, variant)
            rows.append(row)
            if deal.deal_id in pending:
                row.status, row.reason = PENDING, pending[deal.deal_id]
                continue
            if deal.deal_id not in financials:
                raise TransactionsError(f"{deal.deal_id}: faltan las cuentas de referencia")
            fin = financials[deal.deal_id]
            row.currency = fin.currency
            row.reference_period_end = fin.period_end.isoformat()
            if fin.period_end >= deal.announced:
                raise TransactionsError(f"{deal.deal_id}: el ejercicio de referencia cierra el "
                                        f"{fin.period_end}, no antes del anuncio")
            row.borrowings, row.cash, row.net_debt = fin.borrowings, fin.cash, fin.net_debt
            row.related_party_financing = fin.related_party_financing
            row.revenue_ex_player_trading = fin.revenue_ex_player_trading
            row.source_file, row.sha256, row.sources = fin.source_file, fin.sha256, fin.sources
            if fin.note:
                row.note = f"{row.note} {fin.note}".strip()
            if variant.basis == "per_share":
                if not fin.shares_outstanding:
                    raise TransactionsError(f"{deal.deal_id}: el precio es por acción y faltan "
                                            "las acciones del informe de referencia")
                row.shares_outstanding = fin.shares_outstanding
                price = variant.price_per_share * fin.shares_outstanding
            else:
                price = variant.amount
            row.price_amount = _round(price)
            if deal.price_currency != fin.currency:
                if deal.deal_id not in rates:
                    raise TransactionsError(f"{deal.deal_id}: el precio va en "
                                            f"{deal.price_currency} y las cuentas en "
                                            f"{fin.currency}: faltan los tipos del BCE")
                rate = rates[deal.deal_id]
                row.fx_rate, row.fx_date, row.fx_note = float(rate.rate), rate.date, rate.note
                price = price * rate.rate
            if variant.basis == "ev":
                row.ev = _round(price)
                row.equity_value = row.ev - fin.net_debt
            else:
                row.equity_value = _round(price)
                row.ev = row.equity_value + fin.net_debt
            if fin.revenue_ex_player_trading <= 0:
                raise TransactionsError(f"{deal.deal_id}: revenue_ex_player_trading no es "
                                        "positivo")
            row.ev_to_revenue = row.ev / fin.revenue_ex_player_trading
    return rows


TRANSACTIONS_SCHEMA = pa.DataFrameSchema(
    {
        "deal_id": pa.Column(str),
        "variant": pa.Column(str),
        "tier": pa.Column(str, pa.Check.isin(TIERS)),
        "status": pa.Column(str, pa.Check.isin((OK, EXCLUDED, PENDING))),
        "ev": pa.Column("Int64", nullable=True),
        "equity_value": pa.Column("Int64", nullable=True),
        "net_debt": pa.Column("Int64", nullable=True),
        "revenue_ex_player_trading": pa.Column("Int64", nullable=True),
        "ev_to_revenue": pa.Column(float, nullable=True),
        "marks": pa.Column(str),
    },
    checks=[
        # Una operación calculada tiene EV, ingresos y múltiplo, y el múltiplo es EV / ingresos.
        pa.Check(lambda df: (df["status"] != OK) | (
            df["ev"].notna() & df["revenue_ex_player_trading"].notna()
            & ((df["ev_to_revenue"] - df["ev"].astype(float)
                / df["revenue_ex_player_trading"].astype(float)).abs() < 1e-12)),
            element_wise=False, error="múltiplo distinto de EV / ingresos"),
        # EV = equity + deuda neta.
        pa.Check(lambda df: (df["status"] != OK) | (
            df["ev"] == df["equity_value"] + df["net_debt"]),
            element_wise=False, error="EV distinto de equity + deuda neta"),
        # Las de solo prensa van marcadas; las demás, no.
        pa.Check(lambda df: (df["tier"] == "press_only") == df["marks"].str.contains(
            "solo prensa", regex=False), element_wise=False,
            error="marca de solo prensa"),
        # Una excluida o pendiente lleva motivo.
        pa.Check(lambda df: (df["status"] == OK) | (df["reason"].str.len() > 0),
                 element_wise=False, error="excluida o pendiente sin motivo"),
    ],
    unique=["deal_id", "variant"],
)


def to_frame(rows: list[Row]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(row) | {"marks": "; ".join(row.marks)} for row in rows])
    for column in ("price_amount", "shares_outstanding", "equity_value", "borrowings", "cash",
                   "net_debt", "related_party_financing", "ev", "revenue_ex_player_trading"):
        frame[column] = frame[column].astype("Int64")
    for column in ("price_per_share", "fx_rate", "ev_to_revenue"):
        frame[column] = frame[column].astype(float)
    return frame


def validate(frame: pd.DataFrame) -> list[str]:
    try:
        TRANSACTIONS_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return [str(failure) for failure in exc.failure_cases.itertuples(index=False)]
    return []
