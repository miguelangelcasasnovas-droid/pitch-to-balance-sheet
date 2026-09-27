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
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
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


def document(report_year: int, control_index: int | None) -> DocumentSpec:
    """El 20-F presentado en report_year: 2025 (ejercicio 2024/25) o 2026 (2025/26)."""
    columns = tuple(str(report_year - offset) for offset in range(3))
    pnl_page, staff_page = (99, 120) if report_year == 2025 else (101, 122)
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
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025",
                       note=STAFF_NOTE, negate=True),
            FigureSpec("staff_costs_exceptional", (("staff", "termination_benefits"),), "2025",
                       note=EXCEPTIONAL_NOTE, negate=True, included_in_staff_costs="true"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
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
