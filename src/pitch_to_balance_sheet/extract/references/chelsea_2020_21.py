"""Chelsea FC plc (02536231, hoy Chelsea FC Holdings Limited), cuentas del grupo a 30/06/2021 de
Companies House: escaneo, OCR. Ejercicio de referencia de la compra de 2022.

Páginas localizadas a mano en el OCR guardado y en la página renderizada:
- pág. 17 (14 impresa), Group profit and loss account: cuatro columnas en £'000 (operaciones sin
  amortización ni traspasos de jugadores 2021, amortización y traspasos 2021, total 2021 y total
  2020). En Turnover la columna de jugadores está en blanco.
- pág. 19 (16 impresa), Group balance sheet: dos columnas por año, las partidas en la interior
  y los subtotales en la exterior.
- pág. 41 (38 impresa), notas 21 y 22: acreedores a menos y a más de un año, del grupo y de la
  sociedad. No hay préstamos bancarios ni arrendamientos (FRS 102).
- pág. 25 (22 impresa), nota 1.4: «Turnover represents all income ... excluding transfer fees».
- pág. 34 (31 impresa), nota 11: todos los gastos financieros son la actualización de los
  traspasos aplazados. Los importes con la matriz (Fordstam Limited, nota 21) no devengan
  interés y las cuentas no dan calendario de devolución: van a related_party_financing (plan,
  sección 9), no a borrowings.
"""

from pitch_to_balance_sheet.extract import balance
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

PNL_COLUMNS = ("operations_2021", "players_2021", "total_2021", "total_2020")
PNL_ROWS = {
    "turnover": r"^turnover$",
    "cost_of_sales": r"^cost of sales$",
    "gross_profit": r"^gross profit$",
    "administrative_expenses": r"^administrative expenses$",
    "other_operating_income": r"^other operating income$",
    "exceptional_expenses": r"^exceptional administrative expenses$",
    "operating_loss": r"^operating loss$",
    "interest_receivable": r"^interest receivable",
    "interest_payable": r"^interest payable",
    "profit_disposal_players": r"^profit on disposal of player registrations$",
    "fair_value_investment_properties": r"^fair value loss on investment properties$",
    "result_before_tax": r"^\(loss\)/profit before taxation$",
    "tax": r"^taxation$",
    "net_result": r"^\(loss\)/profit for the financial year$",
}
BALANCE_COLUMNS = ("inner_2021", "outer_2021", "inner_2020", "outer_2020")
BALANCE_ROWS = {
    "stocks": r"^stocks$", "debtors": r"^debtors$",
    "cash": r"^cash at bank and in hand$",
    "creditors_current": r"^creditors amounts falling due within one year$",
    "creditors_noncurrent": r"^creditors amounts falling due after more than one year$",
}
GROUP_COMPANY = ("group_2021", "group_2020", "company_2021", "company_2020")
GROUP = GROUP_COMPANY[:2]
CREDITORS_CURRENT = {
    "trade": r"^trade creditors$", "corporation_tax": r"^corporation tax$",
    "tax": r"^other taxation and social security$", "other": r"^other creditors$",
    "parent": r"^amounts owed to parent undertaking$",
    "accruals": r"^accruals and deferred income$",
}
# Derivative financial instruments está en blanco en las cuatro columnas: no tiene cifras.
CREDITORS_NONCURRENT = {"trade": r"^trade creditors$"}

REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 17) separa la columna de amortización y traspasos de "
    "jugadores, y en Turnover esa columna está en blanco; la nota 1.4 (pág. 25) dice que la "
    "cifra de negocio excluye los traspasos."
)
ZERO_NOTE = (
    "0, derivado: los acreedores del grupo de las notas 21 y 22 (pág. 41) no tienen préstamos "
    "(el total de cada nota menos todas sus líneas). Los 29.550 con la matriz Fordstam Limited no "
    "devengan interés (la nota 11, pág. 34, solo tiene la actualización de traspasos aplazados) y "
    "las cuentas no dan su calendario: van a related_party_financing."
)
RELATED_NOTE = (
    "Amounts owed to parent undertaking (nota 21, pág. 41): Fordstam Limited, la matriz, sin "
    "interés ni calendario de devolución en las cuentas."
)

SPEC = ClubSpec(
    club_id="chelsea",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 17, 19 y 41, vistas en la página renderizada. El "
               "OCR lee la £ como € o E: la moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 17, PNL_COLUMNS, PNL_ROWS,
                # Las celdas en blanco no son cifras: los cuadres van en las columnas donde
                # están todas. En el total de 2021, todos; en 2020, sin otros ingresos de
                # explotación (en blanco); y el total = operaciones + jugadores en las filas
                # con las dos partes.
                sums=(
                    Sum("gross_profit", ("turnover", "cost_of_sales"),
                        ("operations_2021", "total_2021", "total_2020")),
                    Sum("operating_loss", ("gross_profit", "administrative_expenses",
                                           "other_operating_income", "exceptional_expenses"),
                        ("operations_2021", "total_2021")),
                    Sum("operating_loss", ("gross_profit", "administrative_expenses",
                                           "exceptional_expenses"), ("total_2020",)),
                    Sum("result_before_tax", ("operating_loss", "interest_receivable",
                                              "interest_payable", "profit_disposal_players",
                                              "fair_value_investment_properties"),
                        ("total_2021", "total_2020")),
                    Sum("net_result", ("result_before_tax", "tax"),
                        ("operations_2021", "total_2021", "total_2020")),
                ),
                cross=(Cross("total_2021", ("operations_2021", "players_2021"),
                             ("administrative_expenses", "operating_loss", "interest_receivable",
                              "result_before_tax", "net_result")),),
            ),
            TableSpec("bs", 19, BALANCE_COLUMNS, BALANCE_ROWS,
                      totals_after={"current_assets": "cash"},
                      sums=(Sum("current_assets", ("stocks", "debtors", "cash"),
                                ("inner_2021", "inner_2020")),)),
            TableSpec("creditors_current", 41, GROUP_COMPANY, CREDITORS_CURRENT,
                      select=r"^amounts owed to parent undertaking$",
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_CURRENT), GROUP),)),
            # El OCR lee la cuarta cabecera de la nota 22 como «6000»: quedan tres columnas, y la
            # de la sociedad 2020 (en blanco) no se usa.
            TableSpec("creditors_noncurrent", 41, GROUP_COMPANY[:3], CREDITORS_NONCURRENT,
                      # La tabla de la nota 22 va desde su cabecera hasta la de la nota 23, y
                      # recoge el título de esta: así se distingue de la nota 21.
                      select=r"^23 deferred taxation$",
                      totals_after={"total": "trade"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT), GROUP),)),
        ),
        links=(
            Link(("creditors_current", "total", "group_2021"),
                 ("bs", "creditors_current", "inner_2021"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2021"),
                 ("bs", "creditors_noncurrent", "outer_2021"), sign=-1),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "total_2021"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "total_2021",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("bs", "cash", "inner_2021"),), "inner_2021",
                       note="Cash at bank and in hand (pág. 19)."),
            *balance.zero_from_lines(
                "borrowings",
                (("creditors_current", "total", tuple(CREDITORS_CURRENT)),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2021", ZERO_NOTE),
            FigureSpec("related_party_financing", (("creditors_current", "parent"),),
                       "group_2021", note=RELATED_NOTE),
        ),
    ),
)
