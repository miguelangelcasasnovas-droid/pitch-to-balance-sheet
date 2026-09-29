"""Valoración por comparables (plan, sección 9), en EUR, a la fecha de valoración.

- Cotizados: capitalización = precio × shares_outstanding (del informe); EV = capitalización +
  deuda neta; múltiplo = EV / revenue_ex_player_trading. El precio, del CSV manual de
  config/market.yaml, se pasa a EUR con el tipo del BCE del mismo día (GBp entre 100 y después
  libras a euros; MANU, de dólares a euros). Un valor sin negociación ese día se marca ilíquido.
- No cotizados: los percentiles 25, 50 y 75 del múltiplo de los pares, por sus ingresos, dan el EV
  implícito; el equity implícito es EV − deuda neta. Sin prima de control: los precios son de
  participaciones minoritarias.
- Percentiles con interpolación lineal entre valores ordenados (el método por defecto de pandas y
  numpy): con n valores, el percentil q está en la posición (n − 1) × q.
- Escenarios (sensibilidades):
  - base: los 8 cotizados y net_debt;
  - large_peers: solo Manchester United, Juventus y Borussia Dortmund;
  - incl_transfers: EV y equity con net_debt_incl_transfers; un par sin ese dato sale del cálculo;
  - incl_related_party: el equity de los clubes con related_party_financing, con esa deuda.
  En todos, los cotizados también reciben un EV implícito, como prueba. La versión principal es
  sin el propio club (leave-one-out, decisión del usuario del 29/09/2026): sus percentiles salen
  de los demás pares, y la desviación es EV real / EV implícito mediano − 1. Con el propio club,
  como referencia.
"""

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import pandera.pandas as pa

from pitch_to_balance_sheet import fx
from pitch_to_balance_sheet.config import Club, load_clubs
from pitch_to_balance_sheet.market import Price
from pitch_to_balance_sheet.metrics import GAP, OK, REVENUE

LARGE_PEERS = ("manchester_united", "juventus", "borussia_dortmund")
SCENARIOS = {  # nombre -> (deuda neta, pares: None = todos los cotizados)
    "base": ("net_debt", None),
    "large_peers": ("net_debt", LARGE_PEERS),
    "incl_transfers": ("net_debt_incl_transfers", None),
    "incl_related_party": ("net_debt_incl_related_party", None),
}
QUANTILES = (0.25, 0.5, 0.75)
NO_CONTROL_PREMIUM = ("Sin prima de control: los múltiplos salen de precios de participaciones "
                      "minoritarias.")


class ValuationError(RuntimeError):
    """Falta un precio, un tipo o una cifra que la valoración necesita."""


def quantile(values: list[float], q: float) -> float:
    """Percentil con interpolación lineal: posición (n − 1) × q en los valores ordenados."""
    if not values:
        raise ValuationError("no hay múltiplos para calcular percentiles")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def _euros(value: Decimal | float) -> int:
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Quote:
    """Precio de un cotizado en EUR y su capitalización."""

    club_id: str
    price: Price
    divisor: int
    fx_rate: Decimal  # unidades de la moneda por 1 EUR (1 en EUR)
    fx_date: str
    fx_note: str
    shares: int
    price_eur: Decimal
    market_cap_eur: int


def quote(club: Club, price: Price, shares: int, rates: dict) -> Quote:
    """El precio en EUR con el tipo del BCE del día del precio, y la capitalización."""
    if price.unit != club.quote_currency:
        raise ValuationError(f"{club.club_id}: el precio viene en {price.unit} y cotiza en "
                             f"{club.quote_currency}")
    currency = price.currency
    local = price.close / club.quote_divisor
    if currency == fx.BASE:
        rate, fx_date, fx_note = Decimal(1), "", "la cotización ya está en EUR"
    else:
        if currency not in rates:
            raise ValuationError(f"{club.club_id}: faltan los tipos {currency} del BCE")
        daily = rates[currency]
        try:
            closing = fx.closing_rate(daily, currency, price.date)
        except fx.FxError as exc:
            raise ValuationError(str(exc)) from exc
        rate, fx_date, fx_note = closing.rate, closing.date, closing.note
    price_eur = local / rate
    return Quote(club.club_id, price, club.quote_divisor, rate, fx_date, fx_note, shares,
                 price_eur, _euros(price_eur * shares))


@dataclass
class Row:
    club_id: str
    season: str
    scenario: str
    role: str  # listed o unlisted
    in_peer_set: bool
    valuation_date: str
    net_debt_metric: str
    price_date: str = ""
    price_close: float | None = None
    price_unit: str = ""  # la unidad de cotización: GBp, USD, EUR
    quote_divisor: int | None = None
    price_source_url: str = ""
    price_source_name: str = ""
    price_retrieved_at: str = ""
    illiquid: str = ""  # motivo, si el valor no se negoció el día del precio
    fx_rate: float | None = None
    fx_date: str = ""
    price_eur: float | None = None
    shares_outstanding: int | None = None
    market_cap_eur: int | None = None
    net_debt_eur: int | None = None
    revenue_eur: int | None = None
    ev_eur: int | None = None
    ev_to_revenue: float | None = None
    peers: str = ""
    n_peers: int | None = None
    multiple_p25: float | None = None
    multiple_p50: float | None = None
    multiple_p75: float | None = None
    ev_implied_p25: int | None = None
    ev_implied_p50: int | None = None
    ev_implied_p75: int | None = None
    equity_implied_p25: int | None = None
    equity_implied_p50: int | None = None
    equity_implied_p75: int | None = None
    # Prueba sobre los cotizados, sin el propio club (la versión principal).
    backtest_multiple_p25: float | None = None
    backtest_multiple_p50: float | None = None
    backtest_multiple_p75: float | None = None
    backtest_ev_implied_p25: int | None = None
    backtest_ev_implied_p50: int | None = None
    backtest_ev_implied_p75: int | None = None
    backtest_deviation: float | None = None  # EV real / EV implícito mediano − 1
    backtest_within_p25_p75: bool | None = None
    # La misma prueba con el propio club entre los pares, como referencia.
    deviation_incl_self: float | None = None
    within_p25_p75_incl_self: bool | None = None
    status: str = OK
    reason: str = ""
    note: str = field(default="")


def _metric(metrics: pd.DataFrame, club_id: str, name: str) -> tuple[int | None, str]:
    rows = metrics[(metrics["club_id"] == club_id) & (metrics["metric"] == name)]
    if rows.empty:
        return None, f"{name} no se calcula para este club"
    row = rows.iloc[0]
    if row["status"] != OK:
        return None, f"{name}: {row['reason']}"
    return int(row["value"]), ""


def _revenue(facts: pd.DataFrame, club_id: str) -> int | None:
    rows = facts[(facts["club_id"] == club_id) & (facts["concept"] == REVENUE)]
    if rows.empty or rows.iloc[0]["is_gap"]:
        return None
    return int(rows.iloc[0]["value_eur"])


def run(facts: pd.DataFrame, metrics: pd.DataFrame, quotes: dict[str, Quote],
        valuation_date: date, season: str = "2024/25") -> list[Row]:
    clubs = [club for club in load_clubs() if club.club_id in set(facts["club_id"])]
    listed = [club.club_id for club in clubs if club.ticker]
    rows = []
    for scenario, (net_debt_metric, peer_ids) in SCENARIOS.items():
        peer_ids = tuple(peer_ids or listed)
        base = []
        for club in clubs:
            net_debt, reason = _metric(metrics, club.club_id, net_debt_metric)
            if scenario == "incl_related_party" and reason:
                continue  # solo los clubes con saldos vinculados fuera de la deuda
            row = Row(club.club_id, season, scenario, "listed" if club.ticker else "unlisted",
                      club.club_id in peer_ids, valuation_date.isoformat(), net_debt_metric,
                      net_debt_eur=net_debt, revenue_eur=_revenue(facts, club.club_id))
            if club.ticker:
                if club.club_id not in quotes:
                    raise ValuationError(f"{club.club_id}: falta su cotización")
                q = quotes[club.club_id]
                row = replace(
                    row, price_date=q.price.date.isoformat(), price_close=float(q.price.close),
                    price_unit=q.price.unit, quote_divisor=q.divisor,
                    price_source_url=q.price.source_url, price_source_name=q.price.source_name,
                    price_retrieved_at=q.price.retrieved_at, illiquid=q.price.illiquid,
                    fx_rate=float(q.fx_rate), fx_date=q.fx_date, price_eur=float(q.price_eur),
                    shares_outstanding=q.shares, market_cap_eur=q.market_cap_eur,
                    note="; ".join(text for text in (q.price.note, q.fx_note) if text))
                if net_debt is not None and row.revenue_eur:
                    row.ev_eur = q.market_cap_eur + net_debt
                    row.ev_to_revenue = row.ev_eur / row.revenue_eur
                else:
                    row.status, row.reason = GAP, reason or f"falta {REVENUE}"
            base.append(row)
        multiples = {row.club_id: row.ev_to_revenue for row in base
                     if row.in_peer_set and row.ev_to_revenue is not None}
        excluded = [f"{row.club_id} (hueco en {net_debt_metric})" for row in base
                    if row.in_peer_set and row.ev_to_revenue is None]
        if scenario == "incl_related_party":  # los múltiplos del caso base
            multiples = {row.club_id: row.ev_to_revenue for row in rows
                         if row.scenario == "base" and row.in_peer_set
                         and row.ev_to_revenue is not None}
        percentiles = [quantile(list(multiples.values()), q) for q in QUANTILES]
        for row in base:
            row.peers = ", ".join(multiples) + (f"; fuera: {', '.join(excluded)}"
                                               if excluded else "")
            row.n_peers = len(multiples)
            row.multiple_p25, row.multiple_p50, row.multiple_p75 = percentiles
            if row.revenue_eur is None:
                row.status, row.reason = GAP, f"falta {REVENUE}"
                rows.append(row)
                continue
            implied = [_euros(Decimal(str(m)) * row.revenue_eur) for m in percentiles]
            row.ev_implied_p25, row.ev_implied_p50, row.ev_implied_p75 = implied
            if row.net_debt_eur is not None:
                (row.equity_implied_p25, row.equity_implied_p50,
                 row.equity_implied_p75) = (ev - row.net_debt_eur for ev in implied)
            elif row.role == "unlisted":
                row.status, row.reason = GAP, _metric(metrics, row.club_id, net_debt_metric)[1]
            if row.role == "unlisted":
                row.note = NO_CONTROL_PREMIUM
            elif row.ev_eur is not None:  # prueba sobre los cotizados
                row.deviation_incl_self = row.ev_eur / row.ev_implied_p50 - 1
                row.within_p25_p75_incl_self = implied[0] <= row.ev_eur <= implied[2]
                others = [m for club_id, m in multiples.items() if club_id != row.club_id]
                if others:
                    loo = [quantile(others, q) for q in QUANTILES]
                    (row.backtest_multiple_p25, row.backtest_multiple_p50,
                     row.backtest_multiple_p75) = loo
                    loo_ev = [_euros(Decimal(str(m)) * row.revenue_eur) for m in loo]
                    (row.backtest_ev_implied_p25, row.backtest_ev_implied_p50,
                     row.backtest_ev_implied_p75) = loo_ev
                    row.backtest_deviation = row.ev_eur / loo_ev[1] - 1
                    row.backtest_within_p25_p75 = loo_ev[0] <= row.ev_eur <= loo_ev[2]
            rows.append(row)
    return rows


def to_frame(rows: list[Row]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(row) for row in rows], columns=list(Row.__dataclass_fields__))
    integers = ["quote_divisor", "shares_outstanding", "market_cap_eur", "net_debt_eur",
                "revenue_eur", "ev_eur", "n_peers", "ev_implied_p25", "ev_implied_p50",
                "ev_implied_p75", "equity_implied_p25", "equity_implied_p50",
                "equity_implied_p75", "backtest_ev_implied_p25", "backtest_ev_implied_p50",
                "backtest_ev_implied_p75"]
    floats = ["price_close", "fx_rate", "price_eur", "ev_to_revenue", "multiple_p25",
              "multiple_p50", "multiple_p75", "backtest_multiple_p25", "backtest_multiple_p50",
              "backtest_multiple_p75", "backtest_deviation", "deviation_incl_self"]
    return frame.astype({**dict.fromkeys(integers, "Int64"), **dict.fromkeys(floats, "float64"),
                         "backtest_within_p25_p75": "boolean",
                         "within_p25_p75_incl_self": "boolean"})


VALUATION_SCHEMA = pa.DataFrameSchema(
    {
        "club_id": pa.Column(str),
        "scenario": pa.Column(str, pa.Check.isin(list(SCENARIOS))),
        "role": pa.Column(str, pa.Check.isin(["listed", "unlisted"])),
        "status": pa.Column(str, pa.Check.isin([OK, GAP])),
    },
    checks=[
        pa.Check(lambda f: ~f.duplicated(["club_id", "season", "scenario"]),
                 error="fila repetida"),
        pa.Check(lambda f: (f["status"] == OK) | (f["reason"].str.len() > 0),
                 error="un hueco lleva su motivo"),
        pa.Check(lambda f: (f["role"] == "unlisted") | f["market_cap_eur"].notna(),
                 error="un cotizado lleva su capitalización"),
        pa.Check(lambda f: f["ev_eur"].isna() | (f["ev_eur"] == f["market_cap_eur"]
                                                 + f["net_debt_eur"]),
                 error="EV = capitalización + deuda neta"),
        pa.Check(lambda f: f["equity_implied_p50"].isna()
                 | (f["equity_implied_p50"] == f["ev_implied_p50"] - f["net_debt_eur"]),
                 error="equity implícito = EV implícito − deuda neta"),
    ],
)


def validate(frame: pd.DataFrame) -> list[str]:
    try:
        VALUATION_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return sorted({str(check) for check in exc.failure_cases["check"]})
    return []
