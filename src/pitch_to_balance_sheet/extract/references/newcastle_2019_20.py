"""Newcastle United Limited, cuentas del grupo del periodo de 13 meses del 01/07/2019 al
31/07/2020, de Companies House: escaneo, OCR. Ejercicio de referencia de la compra de 2021.

El periodo se alargó un mes (AA01 del 28/06/2021): las cifras son de 13 meses y no se anualizan.

Páginas localizadas a mano en el OCR guardado y en la página renderizada:
- pág. 15 (12 impresa), Consolidated statement of income and retained earnings: 13 meses a
  31/07/2020 y año a 30/06/2019, en £000 (el OCR lee las cabeceras como «6000»).
- pág. 16 (13 impresa), Consolidated statement of financial position: dos columnas por año, las
  partidas en la interior y los subtotales en la exterior.
- pág. 27 (24 impresa), nota 4, turnover: matchday, media, commercial y other income (seguros,
  subvenciones e international fees). No hay traspasos ni cesiones.
- pág. 34 (31 impresa), nota 16, y pág. 35 (32 impresa), nota 17: acreedores a menos y a más de
  un año, cada una con OCR de su región (con la página entera el OCR pierde rótulos y cifras).
- pág. 37 (34 impresa), nota 23, Net debt reconciliation: el préstamo del dueño (106.912) «continues
  to be interest free, is repayable on demand». Sin interés ni calendario: va a
  related_party_financing (plan, sección 9), no a borrowings. La nota 27 (pág. 39) lo confirma:
  «No interest was payable on the loans».
- Las obligaciones por arrendamiento financiero y compras a plazos (HP) son arrendamientos: no
  entran en borrowings (plan, sección 9).
"""

from pitch_to_balance_sheet.extract import balance
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    Sum,
    TableSpec,
)

COLUMNS = ("2020", "2019")
# El OCR lee las cabeceras £000 como «6000», «2000» o «€000».
HEADER = r"^[£€$f562],?[0O]{3}$"
THOUSANDS_EVIDENCE = r"(^|\s)[£€f62],?000(\s|$)"
PNL_ROWS = {
    "turnover": r"^turnover$",
    "operating_expenses": r"^operating expenses$",
    "amortisation": r"^amortisation and impairment of players registrations$",
    "operating_result": r"^operating \(loss\)/profit$",
    "profit_disposal_players": r"^profit on disposal of players registrations$",
    "result_before_interest": r"^\(loss\)/profit before interest and taxation$",
    "interest_receivable": r"^interest receivable and similar income$",
    "interest_payable": r"^interest payable and expenses$",
    "result_before_tax": r"^\(loss\)/profit before tax$",
    "tax": r"^tax on \(loss\)/profit$",
    "net_result": r"^\(loss\)/ ?profit and total comprehensive income for the period$",
}
TURNOVER_ROWS = {"matchday": r"^matchday$", "media": r"^media$",
                 "commercial": r"^commercial$", "other_income": r"^other income$"}
BALANCE_COLUMNS = ("inner_2020", "outer_2020", "inner_2019", "outer_2019")
BALANCE_ROWS = {
    "debtors_current": r"^debtors amounts falling due within one year$",
    "debtors_noncurrent": r"^debtors amounts falling due after one year$",
    "cash": r"^cash at bank and in hand$",
    "creditors_current": r"^creditors amounts falling due within one year$",
    # El rótulo acaba en «one» y el total va en la línea siguiente, sin rótulo.
    "creditors_noncurrent_label": r"^creditors amounts falling due after more than one$",
}
# Con las cuatro columnas el OCR descoloca cifras de las notas 16 y 17; con la región del rótulo
# y la columna del grupo 2020, las lee todas.
GROUP_2020 = ("group_2020",)
CREDITORS_CURRENT_REGION = (0.05, 0.58, 0.60, 0.83)
CREDITORS_CURRENT = {
    "leases": r"^obligations under finance leases and hp$",
    "parent": r"^loan note owed to parent company",
    "trade": r"^trade creditors$",
    "group": r"^amounts owed to group undertakings$",
    "corporation_tax": r"^corporation tax$",
    "tax": r"^taxation and social security$",
    "other": r"^other creditors$",
    "accruals": r"^accruals and deferred income$",
}
CREDITORS_NONCURRENT_REGION = (0.05, 0.16, 0.60, 0.36)
CREDITORS_NONCURRENT = {
    "parent": r"^amounts owed to parent company$",
    "leases": r"^obligations under finance leases and hp$",
    "trade": r"^trade creditors$",
    "accruals": r"^accruals and deferred income$",
}

REVENUE_EX_NOTE = (
    "Turnover de 13 meses (01/07/2019 a 31/07/2020), sin anualizar. La nota 4 (pág. 27) lo "
    "desglosa en matchday, media, commercial y other income (seguros, subvenciones e "
    "international fees): no hay traspasos ni cesiones; el resultado por traspasos va aparte "
    "(pág. 15)."
)
ZERO_NOTE = (
    "0, derivado: las notas 16 y 17 (págs. 34 y 35) no tienen préstamos (el total de cada nota "
    "menos todas sus líneas del grupo). El préstamo del dueño (Loan note owed to parent company, "
    "106.912) no devenga interés y es exigible a la vista (nota 23, pág. 37): va a "
    "related_party_financing. Las obligaciones por arrendamiento financiero y HP (250 y 40) son "
    "arrendamientos."
)
RELATED_NOTE = (
    "Loan note owed to parent company (nota 16, pág. 34): préstamo de Mike Ashley y sus "
    "sociedades, «interest free, is repayable on demand» (nota 23, pág. 37)."
)

SPEC = ClubSpec(
    club_id="newcastle",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 15, 16, 27, 34 y 35, vistas en la página "
               "renderizada. El OCR las lee como 6000, 2000 o €000: la moneda no se toma del "
               "OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 15, COLUMNS, PNL_ROWS, header=HEADER,
                select=r"^operating expenses$",
                # La amortización sale dos veces: en la cuenta y en el «Analysed as» de debajo.
                after={"amortisation": PNL_ROWS["operating_expenses"]},
                sums=(
                    Sum("operating_result", ("turnover", "operating_expenses", "amortisation")),
                    Sum("result_before_interest", ("operating_result",
                                                   "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_interest", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec("turnover", 27, COLUMNS, TURNOVER_ROWS,
                      totals_after={"total": "other_income"},
                      sums=(Sum("total", tuple(TURNOVER_ROWS)),)),
            TableSpec("bs", 16, BALANCE_COLUMNS, BALANCE_ROWS, header=HEADER,
                      totals_after={"current_assets": "cash",
                                    "creditors_noncurrent": "creditors_noncurrent_label"},
                      sums=(Sum("current_assets", ("debtors_current", "debtors_noncurrent",
                                                   "cash"), ("inner_2020",)),)),
            TableSpec("creditors_current", 34, GROUP_2020, CREDITORS_CURRENT,
                      region=CREDITORS_CURRENT_REGION, header=HEADER,
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_CURRENT)),)),
            TableSpec("creditors_noncurrent", 35, GROUP_2020, CREDITORS_NONCURRENT,
                      region=CREDITORS_NONCURRENT_REGION, header=HEADER,
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT)),)),
        ),
        links=(
            Link(("turnover", "total", "2020"), ("pnl", "turnover", "2020")),
            Link(("turnover", "total", "2019"), ("pnl", "turnover", "2019")),
            Link(("creditors_current", "total", "group_2020"),
                 ("bs", "creditors_current", "inner_2020"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2020"),
                 ("bs", "creditors_noncurrent", "outer_2020"), sign=-1),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "2020"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "2020",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("bs", "cash", "inner_2020"),), "inner_2020",
                       note="Cash at bank and in hand (pág. 16)."),
            *balance.zero_from_lines(
                "borrowings",
                (("creditors_current", "total", tuple(CREDITORS_CURRENT)),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2020", ZERO_NOTE),
            FigureSpec("related_party_financing", (("creditors_current", "parent"),),
                       "group_2020", note=RELATED_NOTE),
        ),
    ),
)
