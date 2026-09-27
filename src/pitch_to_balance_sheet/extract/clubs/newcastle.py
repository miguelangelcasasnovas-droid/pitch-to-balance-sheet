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
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    LinkSum,
    Sum,
    TableSpec,
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
        ),
        links=(
            *(LinkSum(("pnl", "turnover", year), (("turnover", "total", year),))
              for year in COLUMNS),
            # La cuenta da amortización y deterioro juntos, en negativo.
            *(LinkSum(("pnl", "amortisation", year),
                      tuple(("operating", row, year) for row in OPERATING_ROWS), sign=-1)
              for year in COLUMNS),
            MIX.check(),
        ),
        gaps=MIX.gaps(),
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
        ),
    ),
)
