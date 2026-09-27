"""Manchester City Football Club Limited, 2024/25: PDF digital del club, descargado a mano.

Texto directo con pdfplumber, sin OCR. Páginas localizadas buscando los títulos en el texto:
- pág. 20, Statement of Profit or Loss: cuatro columnas en £000 (operaciones sin traspasos 2025,
  traspasos y amortización 2025, total 2025 y total 2024).
- pág. 37, nota 7, Employees: "aggregate payroll costs", 2025 y 2024 en £000. El total incluye
  los pagos basados en acciones.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025", "total_2024")
PNL_ROWS = {
    "revenue": r"^revenue$",
    "other_operating_income": r"^other operating income$",
    "operating_expenses": r"^operating expenses$",
    "operating_loss": r"^operating loss$",
    "profit_disposal_players": r"^profit on disposal of players registrations$",
    "result_before_interest": r"^profit before interest and taxation$",
    "interest_receivable": r"^interest receivable and similar income$",
    "interest_payable": r"^interest payable and similar charges$",
    "result_before_tax": r"^\(loss\)/profit on ordinary activities before taxation$",
    "tax": r"^taxation$",
    "net_result": r"^\(loss\)/profit on ordinary activities after taxation$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
    "share_based_payments": r"^share-based payments$",
    "staff_costs_total": r"^total$",
}

REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 20) separa la columna de traspasos y amortización, y en "
    "Revenue esa columna es un guion: no hay traspasos ni cesiones."
)

SPEC = ClubSpec(
    club_id="manchester_city",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 20 y 37, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£000",
        tables=(
            TableSpec(
                "pnl", 20, PNL_COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_loss", ("revenue", "other_operating_income",
                                           "operating_expenses")),
                    Sum("result_before_interest", ("operating_loss", "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_interest", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
                cross=(Cross("total_2025", ("operations_2025", "players_2025"),
                             tuple(PNL_ROWS)),),
            ),
            TableSpec(
                "staff", 37, ("2025", "2024"), STAFF_ROWS,
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)[:-1]),),
            ),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025",
                       note="Incluye 531 de pagos basados en acciones."),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
        ),
    ),
)
