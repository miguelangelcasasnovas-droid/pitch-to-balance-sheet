"""Manchester United plc, 2024/25: Form 20-F, con texto. Las cuentas están en libras (£'000);
la acción cotiza en USD.

Decisión del usuario del 27/09/2026 (sección 5 del plan):
- fuente: el 20-F del ejercicio 2024/25, presentado en 2025. Columna "2025".
- control de reexpresión: el 20-F del ejercicio 2025/26, presentado en 2026. Su columna "2025"
  se compara con la fuente y se marca reexpresión si una cifra difiere más de un 1%.

Páginas localizadas buscando los títulos en el texto:
- 20-F 2025: pág. 99 (F-6), Consolidated statement of profit or loss, 2025, 2024 y 2023; pág.
  120, nota 7.1, Employee benefit expenses.
- 20-F 2026: pág. 101 (F-6), 2026, 2025 y 2024; pág. 122, nota 7.1.
La nota 7.1 da los gastos en negativo; aquí van en positivo (cambio de signo anotado).
Fase 3a, en los dos 20-F (2025 / 2026):
- págs. 115 / 117, nota 4.1, ingresos: Commercial (Sponsorship y Retail...), Broadcasting
  (Domestic, European, Other) y Matchday, con el total sin rótulo al final. Mapeo en
  config/line_items.yaml.
- págs. 121 / 123, nota 8, Profit on disposal of intangible assets.
- págs. 128 / 130, nota 16, Intangible assets: el bloque "Year ended 30 June 2025", columna
  Registrations. No tiene línea de deterioro.
Fase 3b, balance al 30/06/2025, en los dos 20-F (2025 / 2026):
- págs. 101-102 / 103-104 (F-8 y F-9), Consolidated balance sheet.
- págs. 134 / 135, nota 19, y 137 / 138, nota 24, en frases: los saldos por traspasos dentro
  de trade receivables y trade payables, con la parte a más de un año.
- págs. 136 / 137, nota 22, en frases: acciones de clase A y B emitidas y acciones de clase A
  en autocartera.
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
    Part,
    Sum,
    TableSpec,
    TextCellSpec,
)

NONCURRENT_LIABILITIES = {
    "deferred_revenue": r"^contract liabilities - deferred revenue",
    "payables": r"^trade and other payables$", "borrowings": r"^borrowings$",
    "leases": r"^lease liabilities$", "derivatives": r"^derivative financial instruments$",
}
CURRENT_LIABILITIES = {
    "deferred_revenue": r"^contract liabilities - deferred revenue",
    "payables": r"^trade and other payables$", "tax": r"^income tax payable$",
    "borrowings": r"^borrowings$", "leases": r"^lease liabilities$",
    "derivatives": r"^derivative financial instruments$", "provisions": r"^provisions$",
}
# Frases de las notas, en cada 20-F: (página, patrón). En el de 2025, la cifra del año y la del
# anterior localizan la frase; en el de 2026, la cifra de 2025 va entre paréntesis.
NOTE_CELLS = {
    2025: {
        ("receivables", "total"): (134, r"football clubs of £(?P<amount>[\d,]+) \(2024: "
                                        r"£59,845,000\) of which"),
        ("receivables", "non_current"): (134, r"^£(?P<amount>[\d,]+) \(2024: £27,930,000\) "
                                              r"is receivable after more than one year"),
        ("payables", "total"): (137, r"acquisition of registrations of £(?P<amount>[\d,]+) "
                                     r"\(2024:\s*$"),
        ("payables", "non_current"): (137, r"^£331,418,000\) of which £(?P<amount>[\d,]+) "
                                           r"\(2024: £175,835,000\) is due"),
        ("shares", "class_a"): (136, r"comprised (?P<amount>[\d,]+) \(2024: 56,699,344\) "
                                     r"Class A"),
        ("shares", "class_b"): (136, r"^(?P<amount>[\d,]+) \(2024: 114,301,320\) Class B"),
        ("shares", "treasury"): (136, r"^(?P<amount>[\d,]+) Class A ordinary shares are "
                                      r"currently held in treasury"),
    },
    2026: {
        ("receivables", "total"): (135, r"football clubs of £[\d,]+ \(2025: "
                                        r"£(?P<amount>[\d,]+)\) of which"),
        ("receivables", "non_current"): (135, r"of which £[\d,]+ \(2025: £(?P<amount>[\d,]+)\) "
                                              r"is receivable"),
        ("payables", "total"): (138, r"acquisition of registrations of £[\d,]+ \(2025: "
                                     r"£(?P<amount>[\d,]+)\) of which"),
        ("payables", "non_current"): (138, r"^\(2025: £(?P<amount>[\d,]+)\) is due after more "
                                           r"than one year"),
        ("shares", "class_a"): (137, r"comprised [\d,]+ \(2025: (?P<amount>[\d,]+)\) Class A"),
        ("shares", "class_b"): (137, r"and [\d,]+ \(2025: (?P<amount>[\d,]+)\) Class B"),
        ("shares", "treasury"): (137, r"^(?P<amount>[\d,]+) Class A ordinary shares are "
                                      r"currently held in treasury"),
    },
}
NOTE_LABELS = {
    ("receivables", "total"): "transfer fees receivable from other football clubs",
    ("receivables", "non_current"): "receivable after more than one year",
    ("payables", "total"): "transfer fees and other associated costs",
    ("payables", "non_current"): "due after more than one year",
    ("shares", "class_a"): "Class A ordinary shares",
    ("shares", "class_b"): "Class B ordinary shares",
    ("shares", "treasury"): "Class A ordinary shares held in treasury",
}
TRANSFER_PAYABLES_NOTE = (
    "Transfer fees and other associated costs de la adquisición de registros, dentro de trade "
    "payables (nota 24), con la parte a más de un año; la corriente es la diferencia. Incluye "
    "los costes asociados (p. ej. agentes)."
)
TRANSFER_RECEIVABLES_NOTE = (
    "Transfer fees receivable from other football clubs, dentro de trade receivables (nota 19), "
    "con la parte a más de un año; la corriente es la diferencia."
)
SHARES_NOTE = (
    "Acciones de clase A y B emitidas al 30/06/2025 (nota 22) menos las 1.682.896 de clase A en "
    "autocartera (nota 23: 1.683 miles al 30/06/2025 y 2024). Las de clase B no cotizan, pero "
    "tienen los mismos derechos económicos que las A."
)

STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries",
    "social_security_costs": r"^social security costs$",
    "share_based_payments": r"^share-based payments",
    "pension_costs": r"^pension costs",
    "termination_benefits": r"^termination benefits recognised in exceptional items",
    "staff_costs_total": r"^total employee benefit expenses including exceptional items$",
}
REVENUE_EX_NOTE = (
    "La nota 4 (pág. 115 del 20-F 2025) desglosa los ingresos en commercial, broadcasting y "
    "matchday, y su política contable (nota 4.3, pág. 117) dice que excluyen los transfer fees: "
    "no hay traspasos ni cesiones."
)
STAFF_NOTE = (
    "Total de la nota 7.1 con las indemnizaciones que la nota clasifica como excepcionales "
    "(34,579); sin ellas, 313,256."
)
EXCEPTIONAL_NOTE = (
    "Termination benefits recognised in exceptional items (nota 7.1): indemnizaciones que el "
    "club clasifica como excepcionales. Están incluidas en staff_costs."
)


REVENUE_ROWS = {
    "sponsorship": r"^sponsorship$",
    "retail": r"^retail, merchandising, apparel & products licensing revenue$",
    "commercial": r"^commercial$",
    "domestic": r"^domestic competitions$",
    "european": r"^european competitions$",
    "broadcasting_other": r"^other$",
    "broadcasting": r"^broadcasting$",
    "matchday": r"^matchday$",
}
DISPOSAL_ROWS = {
    "registrations": r"^profit on disposal of registrations$",
    "loan_income": r"^player loan income$",
}
INTANGIBLE_COLUMNS = ("goodwill", "registrations", "other", "total")
INTANGIBLE_ROWS = {
    "opening": r"^opening net book amount$",
    "additions": r"^additions$",
    "disposals": r"^disposals$",
    "amortization": r"^amortization charge$",
    "closing": r"^closing book amount$",
}
MIX = mix.for_club("manchester_united")
IMPAIRMENT_GAP = (
    "no se publica: la nota 16 de movimientos (pág. 128) no tiene fila de deterioro en el bloque "
    "de 2025 (tampoco el 20-F 2026, pág. 130), y el movimiento cuadra sin ella"
)


def document(report_year: int, control_index: int | None) -> DocumentSpec:
    """El 20-F presentado en report_year: 2025 (ejercicio 2024/25) o 2026 (2025/26)."""
    columns = tuple(str(report_year - offset) for offset in range(3))
    pnl_page, staff_page = (99, 120) if report_year == 2025 else (101, 122)
    revenue_page, disposal_page, intangible_page = ((115, 121, 128) if report_year == 2025
                                                    else (117, 123, 130))
    pnl_rows = {
        "revenue": r"^revenue from contracts with customers$",
        "operating_expenses": r"^operating expenses$",
        "profit_disposal_intangibles": r"^profit on disposal of intangible assets$",
        "operating_result": (r"^operating loss$" if report_year == 2025
                             else r"^operating profit/\(loss\)$"),
        "finance_costs": r"^finance costs$",
        "finance_income": r"^finance income$",
        "net_finance_costs": r"^net finance costs$",
        "result_before_tax": r"^loss before income tax$",
        "tax": r"^income tax credit$",
        "net_result": r"^loss for the year$",
    }
    operating = ("revenue", "operating_expenses", "profit_disposal_intangibles")
    balance_columns = columns[:2]
    assets_page, liabilities_page = (101, 102) if report_year == 2025 else (103, 104)
    if report_year == 2025:  # el 20-F 2025 tiene además "Other operating income"
        pnl_rows["other_operating_income"] = r"^other operating income$"
        operating = ("revenue", "other_operating_income", "operating_expenses",
                     "profit_disposal_intangibles")
    return DocumentSpec(
        method="text",
        unit_evidence=r"£.000",
        control_index=control_index,
        control_kind="restatement",
        tables=(
            TableSpec(
                "pnl", pnl_page, columns, pnl_rows,
                sums=(
                    Sum("operating_result", operating),
                    Sum("net_finance_costs", ("finance_costs", "finance_income")),
                    Sum("result_before_tax", ("operating_result", "net_finance_costs")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "staff", staff_page, columns, STAFF_ROWS,
                select=r"^wages and salaries",
                totals_after={"staff_subtotal": "pension_costs"},
                sums=(
                    Sum("staff_subtotal", ("wages_and_salaries", "social_security_costs",
                                           "share_based_payments", "pension_costs")),
                    Sum("staff_costs_total", ("staff_subtotal", "termination_benefits")),
                ),
            ),
            TableSpec(
                "revenue", revenue_page, columns, REVENUE_ROWS,
                totals_after={"total": "matchday"},
                sums=(
                    Sum("commercial", ("sponsorship", "retail")),
                    Sum("broadcasting", ("domestic", "european", "broadcasting_other")),
                    Sum("total", ("commercial", "broadcasting", "matchday")),
                ),
            ),
            TableSpec(
                "disposals", disposal_page, columns, DISPOSAL_ROWS,
                select=DISPOSAL_ROWS["registrations"], totals_after={"total": "loan_income"},
                sums=(Sum("total", tuple(DISPOSAL_ROWS)),),
            ),
            TableSpec(
                "intangibles", intangible_page, INTANGIBLE_COLUMNS, INTANGIBLE_ROWS,
                block=(r"^year ended 30 june 2025$", r"^closing book amount$"),
                sums=(Sum("closing", ("opening", "additions", "disposals", "amortization")),),
                cross=(Cross("total", ("goodwill", "registrations", "other"),
                             tuple(INTANGIBLE_ROWS)),),
            ),
            # Fase 3b: balance.
            TableSpec("bs_noncurrent_assets", assets_page, balance_columns,
                      {"trade": r"^trade receivables$"},
                      block=(r"^non-current assets$", r"^current assets$")),
            TableSpec("bs_current_assets", assets_page, balance_columns,
                      {"cash": r"^cash and cash equivalents$"},
                      block=(r"^current assets$", r"^total assets$")),
            TableSpec("bs_noncurrent_liabilities", liabilities_page, balance_columns,
                      NONCURRENT_LIABILITIES, totals_after={"total": "derivatives"},
                      block=(r"^non-current liabilities$", r"^current liabilities$"),
                      sums=(Sum("total", tuple(NONCURRENT_LIABILITIES)),)),
            TableSpec("bs_current_liabilities", liabilities_page, balance_columns,
                      CURRENT_LIABILITIES, totals_after={"total": "provisions"},
                      block=(r"^current liabilities$", r"^total equity and liabilities$"),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)),)),
        ),
        text_cells=tuple(
            TextCellSpec(table, key, page, NOTE_LABELS[(table, key)], pattern,
                         scale=1 if table == "shares" else 1000)
            for (table, key), (page, pattern) in NOTE_CELLS[report_year].items()),
        links=(
            *(Link(("revenue", "total", year), ("pnl", "revenue", year)) for year in columns),
            *(Link(("disposals", "total", year), ("pnl", "profit_disposal_intangibles", year))
              for year in columns),
            MIX.check(),
            # Todos los trade receivables a más de un año son saldos por traspasos.
            Link(("receivables", "non_current", "2025"),
                 ("bs_noncurrent_assets", "trade", "2025")),
        ),
        gaps={**MIX.gaps(), "impairment_player_registrations": IMPAIRMENT_GAP},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025",
                       note=STAFF_NOTE, negate=True),
            FigureSpec("staff_costs_exceptional", (("staff", "termination_benefits"),), "2025",
                       note=EXCEPTIONAL_NOTE, negate=True, included_in_staff_costs="true"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "amortization", "registrations"),), "2025",
                       note="Amortization charge de Registrations, bloque de 2025 de la nota 16.",
                       negate=True),
            FigureSpec("profit_on_player_disposals", (("disposals", "registrations"),), "2025",
                       note="Profit on disposal of registrations (nota 8); sin ingresos por "
                            "cesiones en 2025."),
            FigureSpec("player_trading_other_income", (("disposals", "loan_income"),), "2025",
                       note="Player loan income de la nota 8: guion en 2025, cero, respaldado por "
                            "el cuadre de la nota."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Cash and cash equivalents (balance, nota 21)."),
            *balance.split("borrowings", Part("bs_current_liabilities", "borrowings"),
                           Part("bs_noncurrent_liabilities", "borrowings"), "2025",
                           note="Borrowings del balance (nota 25): préstamos y bonos "
                                "(senior secured notes) y la línea de crédito revolving."),
            *balance.split("lease_liabilities", Part("bs_current_liabilities", "leases"),
                           Part("bs_noncurrent_liabilities", "leases"), "2025",
                           note="Lease liabilities del balance (nota 14)."),
            *balance.split("transfer_receivables",
                           (Part("receivables", "total"),
                            Part("receivables", "non_current", sign=-1)),
                           Part("receivables", "non_current"), "2025",
                           total=Part("receivables", "total"), note=TRANSFER_RECEIVABLES_NOTE),
            *balance.split("transfer_payables",
                           (Part("payables", "total"), Part("payables", "non_current", sign=-1)),
                           Part("payables", "non_current"), "2025",
                           total=Part("payables", "total"), note=TRANSFER_PAYABLES_NOTE),
            FigureSpec("shares_outstanding",
                       (Part("shares", "class_a"), Part("shares", "class_b"),
                        Part("shares", "treasury", sign=-1)), "2025", unit="shares",
                       note=SHARES_NOTE),
        ),
    )


SPEC = ClubSpec(
    club_id="manchester_united",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las cuentas del 20-F, en el texto del PDF. La acción cotiza "
               "en USD; las cuentas, en libras.",
    primary=document(2025, None),
    controls=(document(2026, 0),),
)
