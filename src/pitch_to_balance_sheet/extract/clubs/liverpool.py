"""The Liverpool Football Club and Athletic Grounds Limited, 2024/25: OCR.

Fuente: el PDF de la web del club, sin capa de texto pero sin ruido de escáner. Control: el
escaneo de Companies House, con la misma paginación y las mismas tres cifras.
Páginas localizadas a mano mirando la página renderizada, en los dos documentos:
- pág. 14 (12 impresa), Consolidated Profit and Loss Account and Other Comprehensive Income:
  2025 y 2024 en £000.
- pág. 27, nota 4, Staff numbers and costs: "Aggregate amounts for both staff and directors",
  2025 y 2024 en £000.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

COLUMNS = ("2025", "2024")
PNL_ROWS = {
    "turnover": r"^turnover$",
    "cost_of_sales": r"^cost of sales$",
    "gross_profit": r"^gross profit$",
    "administrative_expenses": r"^administrative expenses$",
    "other_operating_income": r"^other operating income$",
    "profit_disposal_players": r"^profit on disposal of registrations$",
    "operating_result": r"^operating profit/\(loss\)$",
    "interest_receivable": r"^interest receivable and similar income$",
    "interest_payable": r"^interest payable and similar expenses$",
    "result_before_tax": r"^profit/\(loss\) before taxation$",
    "tax": r"^tax on profit/\(loss\)$",
    "net_result": r"^profit/\(loss\) for the financial year$",
    "other_comprehensive_income": r"^other comprehensive income for the period$",
    # Rótulo en dos líneas; las cifras van en la segunda.
    "total_comprehensive_income": r"^total comprehensive income.* of the company$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "pension_costs": r"^pension costs$",
}


def document(control_index: int | None) -> DocumentSpec:
    return DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        control_index=control_index,
        tables=(
            TableSpec(
                "pnl", 14, COLUMNS, PNL_ROWS,
                sums=(
                    Sum("gross_profit", ("turnover", "cost_of_sales")),
                    Sum("operating_result", ("gross_profit", "administrative_expenses",
                                             "other_operating_income",
                                             "profit_disposal_players")),
                    Sum("result_before_tax", ("operating_result", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                    Sum("total_comprehensive_income", ("net_result",
                                                       "other_comprehensive_income")),
                ),
            ),
            TableSpec(
                "staff", 27, COLUMNS, STAFF_ROWS,
                select=r"^wages and salaries$",
                totals_after={"staff_costs_total": "pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
        ),
    )


REVENUE_EX_NOTE = (
    "La nota 2 (pág. 26) desglosa el turnover en media, commercial y match day: no hay "
    "traspasos ni cesiones."
)

SPEC = ClubSpec(
    club_id="liverpool",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 14 y 27, vistas en la página renderizada, en los "
               "dos documentos. La moneda no se toma del OCR.",
    primary=document(None),
    controls=(document(0),),
)
