"""The Liverpool Football Club and Athletic Grounds Limited, 2024/25: OCR.

Fuente: el PDF de la web del club, sin capa de texto pero sin ruido de escáner. Control: el
escaneo de Companies House, con la misma paginación y las mismas tres cifras.
Páginas localizadas a mano mirando la página renderizada, en los dos documentos:
- pág. 14 (12 impresa), Consolidated Profit and Loss Account and Other Comprehensive Income:
  2025 y 2024 en £000.
- pág. 27, nota 4, Staff numbers and costs: "Aggregate amounts for both staff and directors",
  2025 y 2024 en £000.
Fase 3a, en los dos documentos:
- pág. 26, nota 2, Turnover by activity: las partidas de ingresos (mapeo en
  config/line_items.yaml); y nota 3, Administrative expenses: amortización y deterioro de
  registrations.
- pág. 19, estado de flujos: "Depreciation, amortisation and impairment" es la suma de las tres
  líneas de la nota 3 (en 2025; la de 2024 lleva además un deterioro de inmovilizado material que
  el OCR del escaneo no lee), y "Profit on disposal of registrations" es la línea de la cuenta.
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    LinkSum,
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


YEARS_HEADER = r"^20(24|25)$"
TURNOVER_ROWS = {
    "media": r"^media$",
    "commercial": r"^commercial$",
    "matchday": r"^match day$",
}
ADMIN_ROWS = {
    "amortisation": r"^amortisation of registrations$",
    "impairment": r"^impairment loss on registrations$",
    "depreciation": r"^depreciation of tangible fixed assets$",
}
CASHFLOW_ROWS = {
    "dai": r"^depreciation, amortisation and impairment[ .]*$",  # el OCR del escaneo lee un punto
    "profit_disposals": r"^profit on disposal of registrations$",
}
MIX = mix.for_club("liverpool")


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
            TableSpec(
                "turnover", 26, COLUMNS, TURNOVER_ROWS, header=YEARS_HEADER,
                select=TURNOVER_ROWS["media"], totals_after={"total": "matchday"},
                sums=(Sum("total", tuple(TURNOVER_ROWS)),),
            ),
            TableSpec(
                "admin", 26, COLUMNS, ADMIN_ROWS, header=YEARS_HEADER,
                select=ADMIN_ROWS["amortisation"],
            ),
            TableSpec(
                "cashflow", 19, COLUMNS, CASHFLOW_ROWS, header=YEARS_HEADER,
                select=CASHFLOW_ROWS["dai"],
            ),
        ),
        links=(
            *(Link(("turnover", "total", year), ("pnl", "turnover", year)) for year in COLUMNS),
            *(Link(("cashflow", "profit_disposals", year), ("pnl", "profit_disposal_players", year),
                   sign=-1) for year in COLUMNS),
            LinkSum(("cashflow", "dai", "2025"),
                    tuple(("admin", row, "2025") for row in ADMIN_ROWS)),
            MIX.check(),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("admin", "amortisation"),), "2025",
                       note="Amortisation of registrations (nota 3)."),
            FigureSpec("impairment_player_registrations", (("admin", "impairment"),), "2025",
                       note="Impairment loss on registrations (nota 3)."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "2025", note="Profit on disposal of registrations."),
        ),
    )


REVENUE_EX_NOTE = (
    "La nota 2 (pág. 26) desglosa el turnover en media, commercial y match day: no hay "
    "traspasos ni cesiones."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
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
