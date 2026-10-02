"""Tablas de revisión de las métricas y la valoración, en millones de EUR."""

import re

import pandas as pd

from pitch_to_balance_sheet.config import load_clubs
from pitch_to_balance_sheet.metrics import NOT_COMPARABLE, OK


def _names() -> dict[str, str]:
    return {club.club_id: club.name for club in load_clubs()}


def _order(club_ids) -> list[str]:
    order = [club.club_id for club in load_clubs()]
    return sorted(set(club_ids), key=lambda c: order.index(c) if c in order else len(order))


def missing(reason: str) -> str:
    """Los conceptos que faltan, para las tablas: el motivo completo está en metrics."""
    concepts = list(dict.fromkeys(re.findall(r"falta (\w+)", reason)))
    return "hueco" + (f" (falta {', '.join(concepts)})" if concepts else "")


def millions(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    text = f"{abs(float(value)) / 1_000_000:,.1f}"
    return f"({text})" if value < 0 else text


def percent(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value) * 100:.1f}%"


def multiple(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):.2f}x"


def _metric_cell(metrics: pd.DataFrame, club_id: str, name: str, formatter) -> str:
    rows = metrics[(metrics["club_id"] == club_id) & (metrics["metric"] == name)]
    if rows.empty:
        return "—"
    row = rows.iloc[0]
    if row["status"] == NOT_COMPARABLE:
        return "no comparable"
    if row["status"] != OK:
        return "hueco"
    return formatter(row["value"])


def metrics_table(metrics: pd.DataFrame) -> str:
    names = _names()
    columns = [("mix_matchday", "Matchday", percent), ("mix_broadcasting", "Broadcasting", percent),
               ("mix_commercial", "Commercial", percent), ("mix_other", "Other", percent),
               ("staff_to_revenue", "Salarios / ingresos", percent),
               ("net_debt", "Deuda neta", millions),
               ("net_debt_to_revenue", "Deuda neta / ingresos", percent),
               ("net_debt_incl_leases_to_revenue", "Con arrendamientos / ingresos", percent),
               ("net_debt_incl_transfers_to_revenue", "Con traspasos netos / ingresos", percent),
               ("scr_approx", "SCR aprox.", percent)]
    lines = ["| Club | " + " | ".join(title for _, title, _ in columns) + " |",
             "|" + " --- |" * (len(columns) + 1)]
    for club_id in _order(metrics["club_id"]):
        lines.append(f"| {names.get(club_id, club_id)} | " + " | ".join(
            _metric_cell(metrics, club_id, name, formatter) for name, _, formatter in columns)
            + " |")
    return "\n".join(lines)


def _scenario(valuation: pd.DataFrame, scenario: str) -> pd.DataFrame:
    return valuation[valuation["scenario"] == scenario].set_index("club_id")


def final_table(valuation: pd.DataFrame, metrics: pd.DataFrame) -> str:
    """Club · EV/ingresos (cotizados) · EV implícito P25–mediana–P75 (no cotizados) · equity
    implícito · salarios/ingresos · deuda neta/ingresos. Escenario base."""
    names = _names()
    base = _scenario(valuation, "base")
    lines = ["| Club | EV / ingresos | EV implícito P25 – mediana – P75 | Equity implícito P25 – "
             "mediana – P75 | Salarios / ingresos | Deuda neta / ingresos |",
             "|" + " --- |" * 6]
    for club_id in _order(base.index):
        row = base.loc[club_id]
        if row["role"] == "listed":
            ev_multiple, implied, equity = multiple(row["ev_to_revenue"]), "—", "—"
            if row["illiquid"]:
                ev_multiple += " (ilíquido)"
        else:
            ev_multiple = "—"
            implied = " – ".join(millions(row[f"ev_implied_{p}"]) for p in ("p25", "p50", "p75"))
            equity = (" – ".join(millions(row[f"equity_implied_{p}"])
                                 for p in ("p25", "p50", "p75"))
                      if pd.notna(row["equity_implied_p50"]) else "hueco")
        lines.append(f"| {names.get(club_id, club_id)} | {ev_multiple} | {implied} | {equity} | "
                     f"{_metric_cell(metrics, club_id, 'staff_to_revenue', percent)} | "
                     f"{_metric_cell(metrics, club_id, 'net_debt_to_revenue', percent)} |")
    return "\n".join(lines)


def listed_table(valuation: pd.DataFrame) -> str:
    names = _names()
    base = _scenario(valuation, "base")
    lines = ["| Club | Cierre | Precio | Fuente del precio | Tipo BCE | Precio en EUR | Acciones "
             "| Capitalización | Deuda neta | EV | Ingresos | EV / ingresos |",
             "|" + " --- |" * 12]
    for club_id in _order(base.index):
        row = base.loc[club_id]
        if row["role"] != "listed":
            continue
        rate = "—" if row["fx_date"] == "" else f"{row['fx_rate']:g} ({row['fx_date']})"
        illiquid = " (ilíquido)" if row["illiquid"] else ""
        lines.append(
            f"| {names.get(club_id, club_id)}{illiquid} | {row['price_date']} | "
            f"{row['price_close']:g} {row['price_unit']} | {row['price_source_name']} | {rate} | "
            f"{row['price_eur']:.4f} | "
            f"{int(row['shares_outstanding']):,} | {millions(row['market_cap_eur'])} | "
            f"{millions(row['net_debt_eur'])} | {millions(row['ev_eur'])} | "
            f"{millions(row['revenue_eur'])} | {multiple(row['ev_to_revenue'])} |")
    return "\n".join(lines)


def sensitivity_table(valuation: pd.DataFrame) -> str:
    """Percentiles de cada escenario y EV/equity implícito mediano de los no cotizados."""
    names = _names()
    lines = ["| Escenario | Pares | Múltiplo P25 – mediana – P75 |", "| --- | --- | --- |"]
    for scenario in ("base", "large_peers", "incl_transfers"):
        rows = _scenario(valuation, scenario)
        if rows.empty:
            continue
        row = rows.iloc[0]
        lines.append(f"| {scenario} | {row['n_peers']}: {row['peers']} | "
                     + " – ".join(multiple(row[f"multiple_{p}"]) for p in ("p25", "p50", "p75"))
                     + " |")
    lines += ["", "| Club | EV implícito mediano: base | EV: solo pares grandes | Equity "
              "implícito mediano: base | Equity: con traspasos netos |",
              "| --- | --- | --- | --- | --- |"]
    base, large, transfers = (_scenario(valuation, s) for s in ("base", "large_peers",
                                                                   "incl_transfers"))
    for club_id in _order(base.index):
        if base.loc[club_id, "role"] != "unlisted":
            continue
        equity_t = transfers.loc[club_id, "equity_implied_p50"]
        lines.append(
            f"| {names.get(club_id, club_id)} | {millions(base.loc[club_id, 'ev_implied_p50'])} | "
            f"{millions(large.loc[club_id, 'ev_implied_p50'])} | "
            f"{millions(base.loc[club_id, 'equity_implied_p50'])} | "
            + (millions(equity_t) if pd.notna(equity_t)
               else missing(transfers.loc[club_id, "reason"])) + " |")
    related = _scenario(valuation, "incl_related_party")
    for club_id in related.index:
        with_related = millions(related.loc[club_id, "equity_implied_p50"])
        lines += ["", f"{names.get(club_id, club_id)}, con related_party_financing en la deuda "
                      f"neta: equity implícito mediano {with_related} (base: "
                      f"{millions(base.loc[club_id, 'equity_implied_p50'])})."]
    return "\n".join(lines)


def backtest_table(valuation: pd.DataFrame, scenario: str = "base") -> str:
    """Prueba sobre los cotizados: EV real frente al implícito, sin el propio club entre los
    pares (la versión principal) y, como referencia, con él."""
    names = _names()
    rows = _scenario(valuation, scenario)
    lines = ["| Club | EV real | Múltiplo de los demás P25 – mediana – P75 | EV implícito P25 – "
             "mediana – P75 | Desviación frente a la mediana | Dentro de P25–P75 | Desviación "
             "con el propio club |", "|" + " --- |" * 7]

    def yes_no(value):
        return "—" if pd.isna(value) else ("sí" if value else "no")

    for club_id in _order(rows.index):
        row = rows.loc[club_id]
        if row["role"] != "listed":
            continue
        lines.append(
            f"| {names.get(club_id, club_id)} | {millions(row['ev_eur'])} | "
            + " – ".join(multiple(row[f"backtest_multiple_{p}"]) for p in ("p25", "p50", "p75"))
            + " | " + " – ".join(millions(row[f"backtest_ev_implied_{p}"])
                                 for p in ("p25", "p50", "p75"))
            + f" | {percent(row['backtest_deviation'])} | "
            f"{yes_no(row['backtest_within_p25_p75'])} | {percent(row['deviation_incl_self'])} |")
    return "\n".join(lines)


def _range(low, mid, high, formatter) -> str:
    return f"{formatter(low)} – {formatter(mid)} – {formatter(high)}"


TIER_LABELS = {"base": "base", "press_only": "solo prensa", "excluded": "fuera"}


def transactions_table(transactions: pd.DataFrame) -> str:
    """Una fila por operación y variante, en la moneda de las cuentas de cada una (millones)."""
    lines = ["| Operación | Grupo | Variante | Ejercicio de ref. (publicado) | Moneda | Precio "
             "publicado | Equity | Deuda neta | EV | Ingresos | EV / ingresos |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in transactions.itertuples(index=False):
        if row.status != "ok":
            lines.append(f"| {row.name} | {TIER_LABELS[row.tier]} | — | — | {row.price_currency}"
                         f" | — | — | — | — | — | {row.status}: {row.reason} |")
            continue
        price = (f"{row.price_per_share:g} {row.price_currency}/acción × "
                 f"{row.shares_outstanding:,} = {millions(row.price_amount)}"
                 if row.basis == "per_share" else
                 f"{millions(row.price_amount)} {row.price_currency} ({row.basis})")
        lines.append(
            f"| {row.name} | {TIER_LABELS[row.tier]} | {row.variant} | {row.reference_season} "
            f"({row.reference_published}) | {row.currency} | {price} | "
            f"{millions(row.equity_value)} | {millions(row.net_debt)} | {millions(row.ev)} | "
            f"{millions(row.revenue_ex_player_trading)} | {multiple(row.ev_to_revenue)} |")
    return "\n".join(lines)


def football_field_table(field: pd.DataFrame) -> str:
    """La tabla final: rango de EV de cada método y el equity mediano de cada uno (millones de
    EUR)."""
    names = _names()
    methods = ("comparables", "large_peers", "transactions")
    lines = ["| Club | EV comparables (P25 – mediana – P75) | EV pares grandes (P25 – mediana – "
             "P75) | EV transacciones base | Equity mediano: comparables | pares grandes | "
             "transacciones |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for club_id in _order(field["club_id"]):
        rows = field[field["club_id"] == club_id].set_index("method")
        ranges = [_range(rows.loc[m, "ev_low"], rows.loc[m, "ev_mid"], rows.loc[m, "ev_high"],
                         millions) for m in methods]
        statistic = rows.loc["transactions", "statistic"]
        ranges[2] += f" ({statistic})"
        equity = [millions(rows.loc[m, "equity_mid"]) for m in methods]
        lines.append(f"| {names.get(club_id, club_id)} | " + " | ".join(ranges + equity) + " |")
    return "\n".join(lines)


def football_field_multiples(field: pd.DataFrame) -> str:
    """Los múltiplos de cada método (iguales para todos los clubes) y sus entradas."""
    first = field[field["club_id"] == field["club_id"].iloc[0]]
    lines = ["| Método | Estadístico | n | Múltiplos | Entradas |",
             "| --- | --- | --- | --- | --- |"]
    for row in first.itertuples(index=False):
        lines.append(f"| {row.method} | {row.statistic} | {row.n} | "
                     f"{_range(row.multiple_low, row.multiple_mid, row.multiple_high, multiple)} | "
                     f"{row.inputs} |")
    return "\n".join(lines)
