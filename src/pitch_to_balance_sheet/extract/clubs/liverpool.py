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

Fase 3b, balance al 31/05/2025 (grupo), en los dos documentos:
- pág. 15, Consolidated Balance Sheet: dos columnas por año, las partidas en la interior y los
  subtotales en la exterior.
- pág. 32, notas 13 y 14: acreedores a menos y a más de un año, con el grupo y la sociedad.
- pág. 33, nota 15: el préstamo de la matriz (FSG) y los préstamos bancarios.
El OCR lee las cabeceras £000 de estas páginas también como 2000, 5000 o $000. Liverpool no
separa los saldos por traspasos (van dentro de trade debtors y trade creditors). FRS 102: sin
pasivos por arrendamiento.
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    LinkSum,
    Part,
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
BALANCE_HEADER = r"^[£€$25]000$"  # £000, que el OCR lee también como 2000, 5000, €000 o $000
BALANCE_COLUMNS = ("inner_2025", "outer_2025", "inner_2024", "outer_2024")
GROUP_COMPANY = ("group_2025", "group_2024", "company_2025", "company_2024")
GROUP = GROUP_COMPANY[:2]
BALANCE_ROWS = {
    "cash": r"^cash at bank and in hand$",
    "creditors_current": r"^creditors amounts falling due within one year$",
    "creditors_noncurrent": r"^creditors amounts falling due after more than$",
}
CREDITORS_CURRENT = ("trade", "parent", "tax", "corporation_tax", "other", "accruals",
                     "deferred_income")
CREDITORS_CURRENT_ANCHORS = {"trade": r"^trade creditors$", "parent": r"^amounts owed to parent$",
                             "deferred_income": r"^deferred income$"}
# La última fila con cifras es el número de página impreso (30), al pie.
CREDITORS_NONCURRENT = ("bank", "trade", "group", "other", "total", "page_number")
CREDITORS_NONCURRENT_ANCHORS = {"bank": r"^bank loans and overdrafts",
                                "trade": r"^trade creditors$", "other": r"^other creditors$"}
LOANS_ROWS = {"intercompany": r"^intercompany loan$", "secured": r"^secured bank loans$",
              "costs": r"^less deferred loan costs$"}
BORROWINGS_NOTE = (
    "Interest-bearing loans and borrowings (nota 15): el préstamo de FSG Football Group, LLC "
    "(sin interés y exigible a la vista, a menos de un año: la nota lo llama intercompany loan y "
    "lo incluye en loans and borrowings) y los préstamos bancarios con garantía, netos de "
    "costes, a más de un año."
)
LEASE_NOTE = (
    "0, derivado: las notas 13 y 14 no tienen pasivos por arrendamiento (el total de cada una "
    "menos todas sus líneas del grupo). " + balance.FRS102_LEASES
)
TRANSFER_GAP = (
    "no se publica: Liverpool no separa los saldos por traspasos, que van dentro de trade "
    "debtors y trade creditors (notas 12 a 14)"
)


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
            # Fase 3b: balance y notas 13 a 15.
            TableSpec("bs", 15, BALANCE_COLUMNS, BALANCE_ROWS, header=BALANCE_HEADER),
            TableSpec("creditors_current", 32, GROUP_COMPANY, {}, header=BALANCE_HEADER,
                      select=r"^amounts owed to parent$",
                      # En la web, las rayas encima y debajo del total se leen como guiones.
                      rows_by_order=(*CREDITORS_CURRENT, "total"), drop_rules=True,
                      anchors=CREDITORS_CURRENT_ANCHORS,
                      sums=(Sum("total", CREDITORS_CURRENT, GROUP),)),
            TableSpec("creditors_noncurrent", 32, GROUP_COMPANY, {}, header=BALANCE_HEADER,
                      select=r"^bank loans and overdrafts", rows_by_order=CREDITORS_NONCURRENT,
                      anchors=CREDITORS_NONCURRENT_ANCHORS,
                      sums=(Sum("total", ("bank", "trade", "other"), GROUP),)),
            TableSpec("loans", 33, GROUP_COMPANY, LOANS_ROWS, header=BALANCE_HEADER,
                      select=r"^intercompany loan$", totals_after={"bank_total": "costs"},
                      sums=(Sum("bank_total", ("secured", "costs"), GROUP),)),
        ),
        links=(
            *(Link(("turnover", "total", year), ("pnl", "turnover", year)) for year in COLUMNS),
            *(Link(("cashflow", "profit_disposals", year), ("pnl", "profit_disposal_players", year),
                   sign=-1) for year in COLUMNS),
            LinkSum(("cashflow", "dai", "2025"),
                    tuple(("admin", row, "2025") for row in ADMIN_ROWS)),
            MIX.check(),
            # Balance: las notas son sus líneas del balance (en negativo), y la nota 15, las de
            # préstamos de las notas 13 y 14.
            Link(("creditors_current", "total", "group_2025"),
                 ("bs", "creditors_current", "inner_2025"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2025"),
                 ("bs", "creditors_noncurrent", "outer_2025"), sign=-1),
            *(Link(("loans", "intercompany", column), ("creditors_current", "parent", column))
              for column in GROUP),
            *(Link(("loans", "bank_total", column), ("creditors_noncurrent", "bank", column))
              for column in GROUP),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
              **balance.gaps("transfer_payables", TRANSFER_GAP),
              **balance.gaps("transfer_receivables", TRANSFER_GAP)},
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
            # Balance al 31/05/2025, columna del grupo.
            FigureSpec("cash", (("bs", "cash", "inner_2025"),), "inner_2025",
                       note="Cash at bank and in hand (pág. 15)."),
            *balance.split("borrowings", Part("loans", "intercompany"),
                           Part("loans", "bank_total"), "group_2025", note=BORROWINGS_NOTE),
            *balance.zero_from_lines(
                "lease_liabilities",
                (("creditors_current", "total", CREDITORS_CURRENT),
                 ("creditors_noncurrent", "total", ("bank", "trade", "other"))),
                "group_2025", LEASE_NOTE),
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
