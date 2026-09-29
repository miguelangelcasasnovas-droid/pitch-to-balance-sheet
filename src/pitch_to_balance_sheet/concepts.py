"""Lista cerrada de conceptos de fact_financials (sección 5 del plan) y cómo se convierte cada uno.

- flow: cuenta de resultados; se convierte con la media de los tipos del año fiscal.
- stock: balance a la fecha de cierre; se convierte con el tipo del día de cierre.
- count: número de acciones; no es una cifra monetaria y no se convierte.
"""

FLOW = "flow"
STOCK = "stock"
COUNT = "count"

INCOME = (
    "revenue_total_reported",
    "revenue_ex_player_trading",
    "revenue_matchday",
    "revenue_broadcasting",
    "revenue_commercial",
    "revenue_other",
    "staff_costs",
    "staff_costs_exceptional",
    "staff_severance_disclosed",
    "net_result",
    "net_result_attributable_parent",
    "amortisation_player_registrations",
    "impairment_player_registrations",
    "profit_on_player_disposals",
    "player_trading_other_income",
)
# Cada concepto de balance con su parte corriente y no corriente, si el club las separa.
SPLIT = ("borrowings", "lease_liabilities", "transfer_payables", "transfer_receivables")
BALANCE = (
    *(f"{concept}{suffix}" for concept in SPLIT for suffix in ("", "_current", "_non_current")),
    "cash",
)
SHARES = ("shares_outstanding",)
# Saldos con sociedades vinculadas que no cumplen la definición de deuda financiera (sin interés ni
# calendario de devolución): fuera de borrowings, solo para una variante de sensibilidad.
RELATED = ("related_party_financing",)

KINDS = {**dict.fromkeys(INCOME, FLOW), **dict.fromkeys(BALANCE, STOCK),
         **dict.fromkeys(RELATED, STOCK), **dict.fromkeys(SHARES, COUNT)}

# Unidad de value_reported -> multiplicador a unidades completas (value_full).
MULTIPLIERS = {"units": 1, "thousands": 1000, "shares": 1, "thousand_shares": 1000,
               # Cifras publicadas con decimales, en la unidad de su último decimal: millones con
               # dos decimales (decenas de miles) o con uno (centenas de miles).
               "ten_thousands": 10_000, "hundred_thousands": 100_000}
