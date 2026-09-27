"""Manchester United plc, 2024/25: Form 20-F 2026, con texto.

Decisión del usuario del 27/09/2026: la fuente es el 20-F 2026. Es el del ejercicio 2025/26, así
que las cifras de 2024/25 salen de su columna comparativa "2025" (ejercicio cerrado el
30/06/2025). La acción cotiza en USD, pero las cuentas están en libras (£'000).
Páginas localizadas buscando los títulos en el texto:
- pág. 101 (F-6), Consolidated statement of profit or loss: 2026, 2025 y 2024 en £'000.
- pág. 122, nota 7.1, Employee benefit expenses: los gastos van en negativo.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)

COLUMNS = ("2026", "2025", "2024")
PNL_ROWS = {
    "revenue": r"^revenue from contracts with customers$",
    "operating_expenses": r"^operating expenses$",
    "profit_disposal_intangibles": r"^profit on disposal of intangible assets$",
    "operating_result": r"^operating profit/\(loss\)$",
    "finance_costs": r"^finance costs$",
    "finance_income": r"^finance income$",
    "net_finance_costs": r"^net finance costs$",
    "result_before_tax": r"^loss before income tax$",
    "tax": r"^income tax credit$",
    "net_result": r"^loss for the year$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries",
    "social_security_costs": r"^social security costs$",
    "share_based_payments": r"^share-based payments",
    "pension_costs": r"^pension costs",
    "termination_benefits": r"^termination benefits",
    "staff_costs_total": r"^total employee benefit expenses including exceptional items$",
}
REVENUE_EX_NOTE = (
    "La nota 4 (pág. 117) desglosa los ingresos en commercial, broadcasting y matchday: no hay "
    "traspasos ni cesiones."
)
STAFF_NOTE = (
    "Total de la nota 7.1 con las indemnizaciones por despido, que la nota clasifica como "
    "partida excepcional (34,579); sin ellas, 313,256."
)

SPEC = ClubSpec(
    club_id="manchester_united",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 101 y 122, en el texto del PDF. La acción cotiza "
               "en USD; las cuentas, en libras.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£.000",
        tables=(
            TableSpec(
                "pnl", 101, COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_result", ("revenue", "operating_expenses",
                                             "profit_disposal_intangibles")),
                    Sum("net_finance_costs", ("finance_costs", "finance_income")),
                    Sum("result_before_tax", ("operating_result", "net_finance_costs")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "staff", 122, COLUMNS, STAFF_ROWS,
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
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
        ),
    ),
)
