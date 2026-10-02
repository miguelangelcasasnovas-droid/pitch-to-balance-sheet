"""Football field de los seis ingleses no cotizados (plan, sección 9; decisión del usuario del
02/10/2026): EV y equity implícitos de cada club con tres métodos.

- comparables: P25, mediana y P75 de EV / ingresos de los 8 cotizados (escenario base de la
  tabla valuation).
- large_peers: lo mismo con los pares grandes (Manchester United, Juventus y Borussia Dortmund).
- transactions: los múltiplos de las transacciones base (tabla transactions). Con menos de 4,
  mínimo, mediana y máximo; con 4 o más, P25, mediana y P75. Cada operación aporta un múltiplo:
  el de su variante de equity (equity o per_share; EV = equity + net_debt).
- transactions_milan_ev: sensibilidad, igual pero con los 1.200 M€ de Milan leídos como EV.

EV implícito = múltiplo × revenue_ex_player_trading del club en EUR, redondeado al euro; equity
implícito = EV − net_debt en EUR. Los múltiplos de las transacciones no tienen moneda: son
EV / ingresos de cada operación en la moneda de sus cuentas. Las de comparables no llevan prima
de control; las transacciones son compras de control (salvo Manchester United, una minoritaria),
así que la incluyen.
"""

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

import pandas as pd
import pandera.pandas as pa

from pitch_to_balance_sheet.valuation import quantile

COMPARABLES, LARGE_PEERS = "comparables", "large_peers"
TRANSACTIONS, TRANSACTIONS_MILAN_EV = "transactions", "transactions_milan_ev"
METHODS = (COMPARABLES, LARGE_PEERS, TRANSACTIONS, TRANSACTIONS_MILAN_EV)
SCENARIOS = {COMPARABLES: "base", LARGE_PEERS: "large_peers"}
EQUITY_BASES = ("equity", "per_share")
MIN_FOR_PERCENTILES = 4
PERCENTILES, MIN_MEDIAN_MAX = "p25-mediana-p75", "mínimo-mediana-máximo"


class FootballFieldError(RuntimeError):
    """Falta un dato para el football field."""


@dataclass
class Range:
    club_id: str
    season: str
    method: str
    statistic: str
    n: int
    inputs: str  # pares o transacciones usados
    multiple_low: float
    multiple_mid: float
    multiple_high: float
    revenue_eur: int
    net_debt_eur: int | None
    ev_low: int
    ev_mid: int
    ev_high: int
    equity_low: int | None
    equity_mid: int | None
    equity_high: int | None
    note: str = ""


def _euros(value: float, revenue: int) -> int:
    return int((Decimal(str(value)) * revenue).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def stats(multiples: list[float]) -> tuple[str, float, float, float]:
    """P25, mediana y P75 con 4 o más múltiplos; si no, mínimo, mediana y máximo."""
    if not multiples:
        raise FootballFieldError("no hay múltiplos")
    if len(multiples) >= MIN_FOR_PERCENTILES:
        return (PERCENTILES, *(quantile(multiples, q) for q in (0.25, 0.5, 0.75)))
    return MIN_MEDIAN_MAX, min(multiples), median(multiples), max(multiples)


def deal_multiples(transactions: pd.DataFrame, milan_as_ev: bool = False) -> dict[str, float]:
    """Un múltiplo por transacción base: el de su variante de equity o, con milan_as_ev, el de
    la variante de EV donde la hay."""
    base = transactions[(transactions["tier"] == "base") & (transactions["status"] == "ok")]
    if base.empty:
        raise FootballFieldError("no hay transacciones base calculadas")
    multiples = {}
    for deal_id, rows in base.groupby("deal_id", sort=False):
        chosen = rows[rows["basis"].isin(EQUITY_BASES)]
        if milan_as_ev and (rows["basis"] == "ev").any():
            chosen = rows[rows["basis"] == "ev"]
        if len(chosen) != 1:
            raise FootballFieldError(f"{deal_id}: tiene que tener una variante de equity (y como "
                                     "mucho una de EV)")
        multiples[deal_id] = float(chosen.iloc[0]["ev_to_revenue"])
    return multiples


def build(valuation: pd.DataFrame, transactions: pd.DataFrame, targets: list[str],
          season: str) -> list[Range]:
    """Los rangos de cada club objetivo con cada método."""
    by_scenario = {scenario: valuation[valuation["scenario"] == scenario].set_index("club_id")
                   for scenario in SCENARIOS.values()}
    deals = {TRANSACTIONS: deal_multiples(transactions),
             TRANSACTIONS_MILAN_EV: deal_multiples(transactions, milan_as_ev=True)}
    ranges = []
    for club_id in targets:
        for method in METHODS:
            if method in SCENARIOS:
                frame = by_scenario[SCENARIOS[method]]
                if club_id not in frame.index:
                    raise FootballFieldError(f"{club_id}: no está en la valoración "
                                             f"({SCENARIOS[method]})")
                row = frame.loc[club_id]
                if pd.isna(row["ev_implied_p50"]):
                    raise FootballFieldError(f"{club_id}: la valoración no tiene EV implícito "
                                             f"({SCENARIOS[method]}): {row['reason']}")
                net_debt = None if pd.isna(row["net_debt_eur"]) else int(row["net_debt_eur"])
                equity = [None if pd.isna(row[f"equity_implied_{p}"])
                          else int(row[f"equity_implied_{p}"]) for p in ("p25", "p50", "p75")]
                ranges.append(Range(
                    club_id, season, method, PERCENTILES, int(row["n_peers"]), row["peers"],
                    float(row["multiple_p25"]), float(row["multiple_p50"]),
                    float(row["multiple_p75"]), int(row["revenue_eur"]), net_debt,
                    int(row["ev_implied_p25"]), int(row["ev_implied_p50"]),
                    int(row["ev_implied_p75"]), *equity, row["note"]))
                continue
            base = by_scenario["base"].loc[club_id]
            revenue = int(base["revenue_eur"])
            net_debt = None if pd.isna(base["net_debt_eur"]) else int(base["net_debt_eur"])
            multiples = deals[method]
            statistic, low, mid, high = stats(list(multiples.values()))
            evs = [_euros(m, revenue) for m in (low, mid, high)]
            equity = [None if net_debt is None else ev - net_debt for ev in evs]
            note = ("Múltiplos de compras de control (Manchester United, minoritaria): incluyen "
                    "la prima que no llevan los comparables.")
            if method == TRANSACTIONS_MILAN_EV:
                note = "Sensibilidad: Milan con los 1.200 M€ como EV. " + note
            ranges.append(Range(
                club_id, season, method, statistic, len(multiples),
                ", ".join(f"{deal} {multiple:.2f}x" for deal, multiple in multiples.items()),
                low, mid, high, revenue, net_debt, *evs, *equity, note))
    return ranges


FOOTBALL_FIELD_SCHEMA = pa.DataFrameSchema(
    {
        "club_id": pa.Column(str),
        "season": pa.Column(str),
        "method": pa.Column(str, pa.Check.isin(METHODS)),
        "statistic": pa.Column(str, pa.Check.isin((PERCENTILES, MIN_MEDIAN_MAX))),
        "n": pa.Column(int, pa.Check.gt(0)),
        "revenue_eur": pa.Column("Int64"),
        "net_debt_eur": pa.Column("Int64", nullable=True),
        "ev_low": pa.Column("Int64"),
        "ev_mid": pa.Column("Int64"),
        "ev_high": pa.Column("Int64"),
        "equity_low": pa.Column("Int64", nullable=True),
        "equity_mid": pa.Column("Int64", nullable=True),
        "equity_high": pa.Column("Int64", nullable=True),
    },
    checks=[
        pa.Check(lambda df: (df["multiple_low"] <= df["multiple_mid"])
                 & (df["multiple_mid"] <= df["multiple_high"]), element_wise=False,
                 error="múltiplos fuera de orden"),
        pa.Check(lambda df: (df["ev_low"] <= df["ev_mid"]) & (df["ev_mid"] <= df["ev_high"]),
                 element_wise=False, error="EV fuera de orden"),
        # Equity = EV − deuda neta, en los tres puntos.
        pa.Check(lambda df: df["net_debt_eur"].isna() | (
            (df["equity_low"] == df["ev_low"] - df["net_debt_eur"])
            & (df["equity_mid"] == df["ev_mid"] - df["net_debt_eur"])
            & (df["equity_high"] == df["ev_high"] - df["net_debt_eur"])),
            element_wise=False, error="equity distinto de EV − deuda neta"),
        # Transacciones: con menos de 4, mínimo-mediana-máximo; con 4 o más, percentiles. Los
        # comparables van siempre con percentiles (también los 3 pares grandes).
        pa.Check(lambda df: df["method"].isin(tuple(SCENARIOS)) | (
            (df["n"] >= MIN_FOR_PERCENTILES) == (df["statistic"] == PERCENTILES)),
            element_wise=False, error="estadístico que no corresponde al número de entradas"),
        pa.Check(lambda df: ~df["method"].isin(tuple(SCENARIOS))
                 | (df["statistic"] == PERCENTILES), element_wise=False,
                 error="los comparables van con percentiles"),
    ],
    unique=["club_id", "season", "method"],
)


def to_frame(ranges: list[Range]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(r) for r in ranges])
    for column in ("revenue_eur", "net_debt_eur", "ev_low", "ev_mid", "ev_high", "equity_low",
                   "equity_mid", "equity_high"):
        frame[column] = frame[column].astype("Int64")
    frame["n"] = frame["n"].astype(int)
    return frame


def validate(frame: pd.DataFrame) -> list[str]:
    try:
        FOOTBALL_FIELD_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return [str(failure) for failure in exc.failure_cases.itertuples(index=False)]
    return []
