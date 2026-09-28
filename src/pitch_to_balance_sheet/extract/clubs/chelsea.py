"""Chelsea FC Holdings Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

Páginas localizadas a mano mirando la página renderizada:
- pág. 17 (14 impresa), Group profit and loss account: cuatro columnas en £'000 (operaciones sin
  amortización ni traspasos de jugadores 2025, amortización y traspasos 2025, total 2025 y total
  2024).
- pág. 34 (31 impresa), nota 8, Employees: remuneración agregada, 2025 y 2024 en £'000. En la
  misma página, la nota 9 (consejeros) tiene otro subtotal, que también se comprueba.
Fase 3a:
- pág. 32 (29 impresa), nota 3, Turnover analysed by class of business: las partidas de
  ingresos (mapeo en config/line_items.yaml).
- pág. 37 (34 impresa), nota 14, Intangible fixed assets del grupo: el bloque "Amortisation and
  impairment", columna Player registrations. El software no tiene deterioro (celda en blanco).

Fase 3b, balance al 30/06/2025 (grupo):
- pág. 19 (16 impresa), Group balance sheet: dos columnas por año, las partidas en la interior
  y los subtotales en la exterior.
- pág. 42 (39 impresa), notas 22 y 23: acreedores a menos y a más de un año, con el grupo y la
  sociedad. Ninguna tiene deuda financiera ni arrendamientos (FRS 102), y Chelsea no separa
  los saldos por traspasos, que van dentro de trade debtors y trade creditors.
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
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
TURNOVER_ROWS = {
    "broadcasting": r"^broadcasting$",
    "commercial": r"^commercial$",
    "matchday": r"^matchday$",
}
INTANGIBLE_ROWS = {
    "opening": r"^at 1 july 2024$",
    "charge": r"^amortisation charged for the year$",
    "impairment": r"^impairment losses$",
    "disposals": r"^disposals$",
    "closing": r"^at 30 june 2025$",
}
MIX = mix.for_club("chelsea")

REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 17) separa la columna de amortización y traspasos de "
    "jugadores, y en Turnover esa columna es un guion: no hay traspasos ni cesiones."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
)


BALANCE_COLUMNS = ("inner_2025", "outer_2025", "inner_2024", "outer_2024")
GROUP_COMPANY = ("group_2025", "group_2024", "company_2025", "company_2024")
GROUP = GROUP_COMPANY[:2]
BALANCE_ROWS = {
    "cash": r"^cash at bank and in hand$",
    "creditors_current": r"^creditors amounts falling due within one year$",
    "creditors_noncurrent": r"^creditors amounts falling due after more than one year$",
}
CREDITORS_CURRENT = {
    "trade": r"^trade creditors$", "group": r"^amounts owed to group undertakings$",
    "corporation_tax": r"^corporation tax payable$",
    "tax": r"^other taxation and social security$", "other": r"^other creditors$",
    "accruals": r"^accruals and deferred income$",
}
CREDITORS_NONCURRENT = {"trade": r"^trade creditors$",
                        "accruals": r"^accruals and deferred income$"}
ZERO_NOTE = (
    "0, derivado: los acreedores del grupo de las notas 22 y 23 no tienen préstamos ni "
    "arrendamientos (el total de cada nota menos todas sus líneas). Los importes con sociedades "
    "del grupo, sin interés y exigibles a la vista (nota 22), son 0 a 30/06/2025 (303.196 en "
    "2024)."
)
TRANSFER_GAP = (
    "no se publica: Chelsea no separa los saldos por traspasos, que van dentro de trade debtors "
    "y trade creditors (notas 21 a 23)"
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
            TableSpec(
                "turnover", 32, NOTE_COLUMNS, TURNOVER_ROWS, select=TURNOVER_ROWS["broadcasting"],
                totals_after={"total": "matchday"},
                sums=(Sum("total", tuple(TURNOVER_ROWS)),),
            ),
            TableSpec(
                "intangibles", 37, ("software", "players", "total"), INTANGIBLE_ROWS,
                block=(r"^amortisation and impairment$", INTANGIBLE_ROWS["closing"]),
                sums=(Sum("closing", ("opening", "charge", "impairment", "disposals"),
                          ("players", "total")),
                      Sum("closing", ("opening", "charge", "disposals"), ("software",))),
                cross=(Cross("total", ("software", "players"),
                             ("opening", "charge", "disposals", "closing")),),
            ),
            # Fase 3b: balance y notas 22 y 23.
            TableSpec("bs", 19, BALANCE_COLUMNS, BALANCE_ROWS),
            TableSpec("creditors_current", 42, GROUP_COMPANY, CREDITORS_CURRENT,
                      select=r"^corporation tax payable$", totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_CURRENT), GROUP),)),
            TableSpec("creditors_noncurrent", 42, GROUP_COMPANY, CREDITORS_NONCURRENT,
                      select=r"^the accruals and deferred income balance represent",
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT), GROUP),)),
        ),
        links=(
            Link(("turnover", "total", "2025"), ("pnl", "turnover", "total_2025")),
            Link(("turnover", "total", "2024"), ("pnl", "turnover", "total_2024")),
            # El deterioro es todo de jugadores: el software no tiene.
            Link(("intangibles", "impairment", "players"), ("intangibles", "impairment", "total")),
            MIX.check(),
            # Cada nota de acreedores es su línea del balance, en negativo.
            Link(("creditors_current", "total", "group_2025"),
                 ("bs", "creditors_current", "inner_2025"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2025"),
                 ("bs", "creditors_noncurrent", "outer_2025"), sign=-1),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
              **balance.gaps("transfer_payables", TRANSFER_GAP),
              **balance.gaps("transfer_receivables", TRANSFER_GAP)},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "charge", "players"),), "2025",
                       note="Amortisation charged for the year de Player registrations (nota 14)."),
            FigureSpec("impairment_player_registrations",
                       (("intangibles", "impairment", "players"),), "2025",
                       note="Impairment losses de Player registrations (nota 14); la nota 5 lo "
                            "llama impairment of player registrations (12,1 millones)."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "total_2025", note="Profit on disposal of player registrations."),
            # Balance al 30/06/2025, columna del grupo.
            FigureSpec("cash", (("bs", "cash", "inner_2025"),), "inner_2025",
                       note="Cash at bank and in hand (pág. 19)."),
            *balance.zero_from_lines(
                "borrowings",
                (("creditors_current", "total", tuple(CREDITORS_CURRENT)),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2025", ZERO_NOTE),
            *balance.zero_from_lines(
                "lease_liabilities",
                (("creditors_current", "total", tuple(CREDITORS_CURRENT)),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2025", ZERO_NOTE + " " + balance.FRS102_LEASES),
        ),
    ),
)
