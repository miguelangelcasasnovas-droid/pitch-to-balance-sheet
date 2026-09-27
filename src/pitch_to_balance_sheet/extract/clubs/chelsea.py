"""Chelsea FC Holdings Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

Páginas localizadas a mano mirando la página renderizada:
- pág. 17 (14 impresa), Group profit and loss account: cuatro columnas en £'000 (operaciones sin
  amortización ni traspasos de jugadores 2025, amortización y traspasos 2025, total 2025 y total
  2024).
- pág. 34 (31 impresa), nota 8, Employees: remuneración agregada, 2025 y 2024 en £'000. En la
  misma página, la nota 9 (consejeros) tiene otro subtotal, que también se comprueba.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025", "total_2024")
PNL_ROWS = {
    "turnover": r"^turnover$",
    "cost_of_sales": r"^cost of sales$",
    "gross_profit": r"^gross profit$",
    "administrative_expenses": r"^administrative expenses$",
    "other_operating_income": r"^other operating income$",
    "operating_loss": r"^operating loss$",
    "interest_receivable": r"^interest receivable",
    "interest_payable": r"^interest payable",
    "profit_disposal_players": r"^profit on disposal of player registrations$",
    "profit_disposal_investments": r"^profit on disposal of fixed asset investments$",
    "disposal_fixed_assets": r"^\(loss\)/profit on disposal of fixed assets$",
    "fair_value_investment_properties": r"^fair value loss on investment properties$",
    # Sic: el PDF rotula "after taxation" la fila que va antes del impuesto.
    "result_before_tax": r"^\(loss\)/profit after taxation$",
    "tax": r"^tax on \(loss\)/profit$",
    "net_result": r"^\(loss\)/profit for the financial year$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "pension_costs": r"^pension costs$",
}
DIRECTORS_ROWS = {
    "directors_remuneration": r"^remuneration for qualifying services$",
    "directors_pension": r"^company pension contributions",
}
NOTE_COLUMNS = ("2025", "2024")

REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 17) separa la columna de amortización y traspasos de "
    "jugadores, y en Turnover esa columna es un guion: no hay traspasos ni cesiones."
)

SPEC = ClubSpec(
    club_id="chelsea",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 17 y 34, vistas en la página renderizada, e "
               "importes en £ del texto de la pág. 17. El OCR lee la £ como €: la moneda no "
               "se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 17, PNL_COLUMNS, PNL_ROWS,
                sums=(
                    Sum("gross_profit", ("turnover", "cost_of_sales")),
                    Sum("operating_loss", ("gross_profit", "administrative_expenses",
                                           "other_operating_income")),
                    Sum("result_before_tax", ("operating_loss", "interest_receivable",
                                              "interest_payable", "profit_disposal_players",
                                              "profit_disposal_investments",
                                              "disposal_fixed_assets",
                                              "fair_value_investment_properties")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
                cross=(Cross("total_2025", ("operations_2025", "players_2025"),
                             tuple(PNL_ROWS)),),
            ),
            TableSpec(
                "staff", 34, NOTE_COLUMNS, STAFF_ROWS,
                totals_after={"staff_costs_total": "pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
                select=r"^wages and salaries$",
            ),
            TableSpec(
                "directors", 34, NOTE_COLUMNS, DIRECTORS_ROWS,
                totals_after={"directors_total": "directors_pension"},
                sums=(Sum("directors_total", tuple(DIRECTORS_ROWS)),),
                select=r"^company pension",
            ),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
        ),
    ),
)
