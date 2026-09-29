"""Métricas por club y temporada (plan, sección 9), en EUR, sobre fact_financials.

- Mix de ingresos: matchday, broadcasting, commercial y other sobre revenue_ex_player_trading.
- Salarios / ingresos: staff_costs / revenue_ex_player_trading.
- Deuda neta (decidida por el usuario el 29/09/2026):
  - net_debt, la principal: borrowings − cash, sin arrendamientos, porque FRS 102 no los reconoce;
  - net_debt_incl_leases: + lease_liabilities, solo en clubes que reconocen los arrendamientos
    (NIIF y FRS 101); en FRS 102 es «no comparable», no 0;
  - net_debt_incl_transfers: net_debt + transfer_payables − transfer_receivables;
  - net_debt_incl_related_party: net_debt + related_party_financing, solo en los clubes que lo
    tienen (variante de sensibilidad).
  Y cada una sobre revenue_ex_player_trading.
- SCR aproximado: hueco hasta tener 2022/23 y 2023/24.

Las cifras monetarias van en euros (value_eur): la cuenta de resultados, con la media del año
fiscal, y el balance, con el tipo de cierre. Una métrica que necesita un hueco es hueco, y dice
cuál; una que no tiene sentido en el marco contable del club es «no comparable».
"""

from dataclasses import asdict, dataclass

import pandas as pd
import pandera.pandas as pa

from pitch_to_balance_sheet.config import load_clubs

OK, GAP, NOT_COMPARABLE = "ok", "gap", "not_comparable"
SCR_GAP = "faltan 2022/23 y 2023/24 para el promedio de traspasos a 3 años"
FRS102_LEASES = ("FRS 102: los arrendamientos operativos no se reconocen en el balance, así que "
                 "la cifra no se puede comparar con la de los clubes NIIF")
REVENUE = "revenue_ex_player_trading"
MIX = ("revenue_matchday", "revenue_broadcasting", "revenue_commercial", "revenue_other")
# Deudas netas: nombre -> términos (signo, concepto) de fact_financials.
NET_DEBTS = {
    "net_debt": ((1, "borrowings"), (-1, "cash")),
    "net_debt_incl_leases": ((1, "borrowings"), (1, "lease_liabilities"), (-1, "cash")),
    "net_debt_incl_transfers": ((1, "borrowings"), (-1, "cash"), (1, "transfer_payables"),
                                (-1, "transfer_receivables")),
    "net_debt_incl_related_party": ((1, "borrowings"), (-1, "cash"),
                                    (1, "related_party_financing")),
}


@dataclass(frozen=True)
class Metric:
    club_id: str
    season: str
    metric: str
    value: float | None
    unit: str  # "ratio" o "EUR"
    status: str  # ok, gap o not_comparable
    reason: str
    formula: str
    components: str  # cada término en EUR


def _inputs(group: pd.DataFrame) -> dict[str, tuple[int | None, str]]:
    """Concepto -> (value_eur, motivo del hueco) de un club y temporada."""
    return {row.concept: (None if row.is_gap or pd.isna(row.value_eur) else int(row.value_eur),
                          row.gap_reason)
            for row in group.itertuples()}


def _missing(values: dict, concepts) -> str:
    """El motivo si falta algún concepto: su hueco o que el club no lo tiene."""
    reasons = []
    for concept in concepts:
        value, reason = values.get(concept, (None, "no está en fact_financials"))
        if value is None:
            reasons.append(f"falta {concept} ({reason})")
    return "; ".join(reasons)


def _combination(values: dict, terms) -> tuple[int | None, str, str]:
    """Suma de los términos (signo, concepto) en EUR, con sus componentes; o el motivo."""
    reason = _missing(values, [concept for _, concept in terms])
    if reason:
        return None, "", reason
    total = sum(sign * values[concept][0] for sign, concept in terms)
    components = " ".join(f"{'−' if sign < 0 else '+'} {concept} {values[concept][0]:,}"
                          for sign, concept in terms).removeprefix("+ ")
    return total, components, ""


def compute(frame: pd.DataFrame) -> list[Metric]:
    clubs = {club.club_id: club for club in load_clubs()}
    metrics = []
    for (club_id, season), group in frame.groupby(["club_id", "season"], sort=False):
        metrics += _club_metrics(club_id, season, _inputs(group),
                                 clubs[club_id].recognises_leases)
    return metrics


def _club_metrics(club_id: str, season: str, values: dict,
                  recognises_leases: bool) -> list[Metric]:
    metrics = []
    revenue = values.get(REVENUE, (None, ""))[0]

    def add(metric, value, unit, formula, components="", reason="", status=None):
        status = status or (OK if value is not None else GAP)
        metrics.append(Metric(club_id, season, metric, value, unit, status,
                              "" if status == OK else reason, formula, components))

    def ratio(metric, numerator, numerator_name, formula, reason="", status=OK):
        """numerator / revenue_ex_player_trading, o el hueco del numerador o de los ingresos."""
        if status == NOT_COMPARABLE:
            add(metric, None, "ratio", formula, reason=reason, status=NOT_COMPARABLE)
            return
        reason = reason or _missing(values, [REVENUE])
        if not reason and not revenue:
            reason = f"{REVENUE} es 0"
        if reason:
            add(metric, None, "ratio", formula, reason=reason)
            return
        add(metric, numerator / revenue, "ratio", formula,
            f"{numerator_name} {numerator:,} / {REVENUE} {revenue:,}")

    for concept in (*MIX, "staff_costs"):
        name = "staff_to_revenue" if concept == "staff_costs" else (
            "mix_" + concept.removeprefix("revenue_"))
        ratio(name, values.get(concept, (None, ""))[0], concept, f"{concept} / {REVENUE}",
              reason=_missing(values, [concept]))

    for name, terms in NET_DEBTS.items():
        formula = " ".join(f"{'−' if sign < 0 else '+'} {concept}"
                           for sign, concept in terms).removeprefix("+ ")
        if name == "net_debt_incl_related_party" and "related_party_financing" not in values:
            continue  # solo en los clubes que tienen esos saldos
        if name == "net_debt_incl_leases" and not recognises_leases:
            add(name, None, "EUR", formula, reason=FRS102_LEASES, status=NOT_COMPARABLE)
            ratio(f"{name}_to_revenue", None, name, f"{name} / {REVENUE}",
                  reason=FRS102_LEASES, status=NOT_COMPARABLE)
            continue
        total, components, reason = _combination(values, terms)
        add(name, total, "EUR", formula, components, reason)
        if name != "net_debt_incl_related_party":
            ratio(f"{name}_to_revenue", total, name, f"{name} / {REVENUE}", reason=reason)
    add("scr_approx", None, "ratio", "(staff_costs + amortisation_player_registrations) / "
        "(revenue + promedio a 3 años de traspasos, otros ingresos de jugadores y deterioro)",
        reason=SCR_GAP)
    return metrics


def to_frame(metrics: list[Metric]) -> pd.DataFrame:
    columns = list(Metric.__dataclass_fields__)
    frame = pd.DataFrame([asdict(metric) for metric in metrics], columns=columns)
    return frame.astype({"value": "float64"})


METRICS_SCHEMA = pa.DataFrameSchema(
    {
        "club_id": pa.Column(str),
        "season": pa.Column(str),
        "metric": pa.Column(str),
        "value": pa.Column(float, nullable=True),
        "unit": pa.Column(str, pa.Check.isin(["ratio", "EUR"])),
        "status": pa.Column(str, pa.Check.isin([OK, GAP, NOT_COMPARABLE])),
        "reason": pa.Column(str),
        "formula": pa.Column(str, pa.Check.str_length(min_value=1)),
        "components": pa.Column(str),
    },
    checks=[
        pa.Check(lambda f: ~f.duplicated(["club_id", "season", "metric"]),
                 error="métrica repetida"),
        pa.Check(lambda f: (f["status"] == OK) == f["value"].notna(),
                 error="una métrica ok lleva valor y una que no lo es, no"),
        pa.Check(lambda f: (f["status"] == OK) | (f["reason"].str.len() > 0),
                 error="un hueco o un «no comparable» lleva su motivo"),
    ],
    strict=True,
)


def validate(frame: pd.DataFrame) -> list[str]:
    try:
        METRICS_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return sorted({str(check) for check in exc.failure_cases["check"]})
    return []
