"""Newcastle United Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

Páginas localizadas a mano mirando la página renderizada:
- pág. 19 (16 impresa), Consolidated statement of comprehensive income: 2025 y 2024 en £000.
  El OCR se hace sobre la región de la tabla.
- pág. 36 (33 impresa), nota 7, Employees: "Staff costs were as follows", 2025 y 2024 en £000.
Fase 3a, en la pág. 35 (32 impresa), con OCR de región:
- nota 4, turnover by class of business: las partidas de ingresos (mapeo en
  config/line_items.yaml). Con la página entera el OCR descoloca las cifras de 2025; con la
  región de la tabla lee todas, pero el rótulo UEFA sale "VEFAR": filas por su orden, con anclas.
- nota 5, operating profit: amortización y deterioro de intangibles (solo derechos de jugadores,
  nota 12), que suman la línea de la cuenta.

Fase 3b, balance al 30/06/2025 (grupo):
- pág. 20 (17 impresa), Consolidated statement of financial position: dos columnas por año, las
  partidas en la interior y los subtotales en la exterior.
- pág. 42 (39 impresa), nota 15, deudores: los de menos de un año con OCR de la región de la
  tabla, sin las columnas de la sociedad; los de más de un año, en su línea del texto, que el
  OCR de la tabla descoloca.
- pág. 43 (40 impresa), notas 16 y 17, acreedores, cada una con OCR de su región. Con la página
  entera el OCR lee «23,000» donde la imagen dice 23,990 (acreedores por traspasos a más de un
  año); el cuadre con el total, 36,084, lo detecta.
FRS 102: sin pasivos por arrendamiento.
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
    TextCellSpec,
)

COLUMNS = ("2025", "2024")
# La tabla de la pág. 19, de los años a la última fila. Con la página entera el OCR pierde los
# rótulos de tres filas; con esta región, no.
PNL_REGION = (0.08, 0.20, 0.97, 0.62)
# El OCR lee las cabeceras £000 como "f000", "6000", "2000" o "6,000": las columnas salen de la
# fila de años, y la prueba de que la unidad son miles admite esas lecturas.
YEARS_HEADER = r"^20(24|25)$"
THOUSANDS_EVIDENCE = r"(^|\s)[£€f62],?000(\s|$)"
# El OCR lee mal los rótulos de este escaneo (tipografía Garamond), y de forma inestable: un
# píxel de diferencia en el recorte cambia el texto ("Turnorer", "Pot on digest of managi fised
# asces"). Por eso las filas se identifican por su orden, con la primera y la última como
# anclas; los cuadres comprueban que cada cifra está en su fila.
PNL_ORDER = (
    "turnover",
    "operating_expenses",
    "operating_result_before_amortisation",
    "amortisation",
    "operating_loss_before_disposals",
    "profit_disposal_players",
    "profit_disposal_subsidiary",
    "profit_disposal_tangibles",
    "operating_profit",
    "interest_receivable",
    "interest_payable",
    "result_before_tax",
    "tax",
    "net_result",
)
PNL_ANCHORS = {"turnover": r"^turno", "net_result": r"total comprehensive income"}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
}

TURNOVER_REGION = (0.10, 0.47, 0.90, 0.59)
TURNOVER_ORDER = ("matchday", "media", "uefa", "commercial", "other_income", "total")
TURNOVER_ANCHORS = {"matchday": r"^matchday$", "media": r"^media$", "total": r"^$"}
OPERATING_REGION = (0.05, 0.66, 0.97, 0.80)
OPERATING_ROWS = {
    "amortisation": r"^amortisation of intangible assets$",
    "impairment": r"^impairment of intangible assets$",
}
MIX = mix.for_club("newcastle")
REVENUE_EX_NOTE = (
    "La nota 4 (pág. 35) desglosa el turnover en matchday, media, UEFA, commercial y other "
    "income (créditos fiscales de I+D, subvenciones e international fees): no hay traspasos "
    "ni cesiones."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
)


BALANCE_HEADER = r"^[£€$56]?[0O]{3}$"  # £000, que el OCR lee también como 5000, 6000 o €000
BALANCE_COLUMNS = ("inner_2025", "outer_2025", "inner_2024", "outer_2024")
BALANCE_ROWS = {
    # El OCR lee «year» como «yeas» o «reat» y «bank» como «bark».
    "debtors_current": r"^debtors amounts falling due within one yea",
    "debtors_noncurrent": r"^debtors amounts falling due afte",
    "cash": r"^cash at ba\S+ and in hand$",
    "creditors_current": r"^creditors amounts falling due w\S*ithin one year$",
    "creditors_noncurrent": r"^creditors amounts falling due after more than one$",
}
DEBTORS_REGION = (0.14, 0.22, 0.70, 0.42)
DEBTORS_ORDER = ("trade", "parent", "group", "transfers", "corporation_tax", "other",
                 "prepayments", "total")
DEBTORS_ANCHORS = {"trade": r"^trade debtors$", "transfers": r"^transfer fees rece",
                   "prepayments": r"^prepayments and accrued income$"}
CREDITORS_CURRENT_REGION = (0.14, 0.20, 0.58, 0.41)  # solo la columna del grupo de 2025
CREDITORS_CURRENT_ORDER = ("term_loan", "trade", "transfers", "tax", "corporation_tax", "other",
                           "accruals", "total")
CREDITORS_CURRENT_ANCHORS = {"term_loan": r"^term loan$", "trade": r"^trade creditors\b",
                             "transfers": r"^transfer fees parable\b",
                             "accruals": r"^accruals and deferred income\b"}
CREDITORS_NONCURRENT_REGION = (0.14, 0.48, 0.86, 0.62)
CREDITORS_NONCURRENT = {"term_loan": r"^term loan$", "transfers": r"^transfer fees payable$",
                        "accruals": r"^accruals and deferred income"}
GROUP_COMPANY = ("group_2025", "group_2024", "company_2025", "company_2024")
BORROWINGS_NOTE = (
    "Term loan (nota 16): el préstamo a plazo de 50 millones, neto de costes, y la línea de "
    "crédito revolving de 8,33 millones, dispuestos al cierre y devueltos después (notas 17 y "
    "28). A más de un año, un guion."
)
LEASE_NOTE = (
    "0, derivado: las notas 16 y 17 no tienen pasivos por arrendamiento (el total de cada una "
    "menos todas sus líneas del grupo). " + balance.FRS102_LEASES
)

SPEC = ClubSpec(
    club_id="newcastle",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 19 y 36, vistas en la página renderizada. La "
               "moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 19, COLUMNS, {}, region=PNL_REGION, header=YEARS_HEADER,
                rows_by_order=PNL_ORDER, anchors=PNL_ANCHORS,
                sums=(
                    Sum("operating_result_before_amortisation", ("turnover",
                                                                 "operating_expenses")),
                    Sum("operating_loss_before_disposals", ("operating_result_before_amortisation",
                                                            "amortisation")),
                    Sum("operating_profit", ("operating_loss_before_disposals",
                                             "profit_disposal_players",
                                             "profit_disposal_subsidiary",
                                             "profit_disposal_tangibles")),
                    Sum("result_before_tax", ("operating_profit", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "staff", 36, COLUMNS, STAFF_ROWS, header=YEARS_HEADER,
                select=r"^wages and salaries$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
            TableSpec(
                "turnover", 35, COLUMNS, {}, region=TURNOVER_REGION, header=YEARS_HEADER,
                rows_by_order=TURNOVER_ORDER, anchors=TURNOVER_ANCHORS,
                sums=(Sum("total", TURNOVER_ORDER[:-1]),),
            ),
            TableSpec(
                "operating", 35, COLUMNS, OPERATING_ROWS, region=OPERATING_REGION,
                header=YEARS_HEADER, select=OPERATING_ROWS["amortisation"],
            ),
            # Fase 3b: balance y notas 15 a 17.
            TableSpec("bs", 20, BALANCE_COLUMNS, BALANCE_ROWS, header=BALANCE_HEADER),
            TableSpec("debtors_current", 42, COLUMNS, {}, region=DEBTORS_REGION,
                      rows_by_order=DEBTORS_ORDER, anchors=DEBTORS_ANCHORS,
                      sums=(Sum("total", DEBTORS_ORDER[:-1]),)),
            # Con más columnas, el OCR no lee el guion de 2024 del term loan.
            TableSpec("creditors_current", 43, ("group_2025",), {},
                      region=CREDITORS_CURRENT_REGION, rows_by_order=CREDITORS_CURRENT_ORDER,
                      anchors=CREDITORS_CURRENT_ANCHORS,
                      sums=(Sum("total", CREDITORS_CURRENT_ORDER[:-1]),)),
            TableSpec("creditors_noncurrent", 43, GROUP_COMPANY, CREDITORS_NONCURRENT,
                      region=CREDITORS_NONCURRENT_REGION, totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT),
                                ("group_2025", "group_2024")),)),
        ),
        text_cells=(
            # Deudores a más de un año, localizados con la cifra de 2024.
            TextCellSpec("debtors_noncurrent", "transfers", 42, "Transfer fees receivable",
                         r"^Transfer fees receivable (?P<amount>[\d,]+) 21,625$"),
            TextCellSpec("debtors_noncurrent", "prepayments", 42,
                         "Prepayments and accrued income",
                         r"^Prepayments and accrued income (?P<amount>[\d,]+) 310$"),
        ),
        links=(
            *(LinkSum(("pnl", "turnover", year), (("turnover", "total", year),))
              for year in COLUMNS),
            # La cuenta da amortización y deterioro juntos, en negativo.
            *(LinkSum(("pnl", "amortisation", year),
                      tuple(("operating", row, year) for row in OPERATING_ROWS), sign=-1)
              for year in COLUMNS),
            MIX.check(),
            # Balance: cada nota es su línea del balance (los acreedores, en negativo).
            Link(("debtors_current", "total", "2025"), ("bs", "debtors_current", "inner_2025")),
            LinkSum(("bs", "debtors_noncurrent", "inner_2025"),
                    (("debtors_noncurrent", "transfers", "2025"),
                     ("debtors_noncurrent", "prepayments", "2025"))),
            Link(("creditors_current", "total", "group_2025"),
                 ("bs", "creditors_current", "inner_2025"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2025"),
                 ("bs", "creditors_noncurrent", "outer_2025"), sign=-1),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("operating", "amortisation"),),
                       "2025", note="Amortisation of intangible assets (nota 5): los intangibles "
                                    "son derechos de jugadores (nota 12)."),
            FigureSpec("impairment_player_registrations", (("operating", "impairment"),), "2025",
                       note="Impairment of intangible assets (nota 5): derechos de jugadores."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "2025", note="Profit on disposal of players' registrations (cuenta)."),
            # Balance al 30/06/2025, columna del grupo.
            FigureSpec("cash", (("bs", "cash", "inner_2025"),), "inner_2025",
                       note="Cash at bank and in hand (pág. 20)."),
            *balance.split("borrowings", Part("creditors_current", "term_loan"),
                           Part("creditors_noncurrent", "term_loan"), "group_2025",
                           note=BORROWINGS_NOTE),
            *balance.zero_from_lines(
                "lease_liabilities",
                (("creditors_current", "total", CREDITORS_CURRENT_ORDER[:-1]),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2025", LEASE_NOTE),
            *balance.split("transfer_payables", Part("creditors_current", "transfers"),
                           Part("creditors_noncurrent", "transfers"), "group_2025",
                           note="Transfer fees payable (notas 16 y 17), netos de su actualización "
                                "(483 y 1.928; en bruto, 65.401 y 25.918)."),
            *balance.split("transfer_receivables", Part("debtors_current", "transfers", "2025"),
                           Part("debtors_noncurrent", "transfers", "2025"), "group_2025",
                           note="Transfer fees receivable (nota 15), a menos y a más de un año."),
        ),
    ),
)
