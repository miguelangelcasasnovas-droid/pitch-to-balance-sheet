"""Arsenal Holdings Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

Páginas localizadas a mano mirando la página renderizada:
- pág. 23, Consolidated profit and loss account: seis columnas en £'000 (operaciones sin
  traspasos, traspasos y total, de 2025 y de 2024). De "Net finance charges" hacia abajo solo
  hay cifras en las columnas de total: esas filas se cuadran solo ahí. El OCR se hace sobre la
  región de la tabla.
- pág. 34, nota 6, Employees: "Staff costs", 2025 y 2024 en £'000.

"Group turnover" incluye en la columna de traspasos 454 de "player trading", que según la nota
de la propia página son sobre todo ingresos por cesiones.

Fase 3a:
- pág. 32, nota 3, Group turnover: las partidas de ingresos, con el mismo player trading de 454
  (mapeo en config/line_items.yaml).
- pág. 33, nota 4, Operating expenses: amortización y deterioro de player registrations (el
  deterioro solo tiene cifra en 2025).

Fase 3b, balance al 31/05/2025 (grupo y sociedad; se usa el grupo):
- pág. 24, Balance sheet: la caja y los acreedores a menos y a más de un año.
- pág. 39, notas 15 y 16: los acreedores, con el préstamo de la matriz y las debentures; y la
  frase de la nota 15 con los saldos por traspasos dentro de other creditors.
- pág. 38, nota 13: la frase con los saldos por traspasos dentro de other debtors.
Las dos frases dan el importe en millones con un decimal y no lo separan en corriente y no
corriente. FRS 102: sin pasivos por arrendamiento.
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
    Part,
    SentenceFigureSpec,
    Sum,
    TableSpec,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025",
               "operations_2024", "players_2024", "total_2024")
TOTALS = ("total_2025", "total_2024")
PNL_ROWS = {
    # Rótulo en dos líneas; las cifras van en la segunda.
    "turnover_including_jv": r"^turnover of the group including its share of joint ventures$",
    "share_of_jv_turnover": r"^share of turnover of joint venture$",
    "group_turnover": r"^group turnover$",
    "operating_expenses": r"^operating expenses$",
    "operating_result": r"^operating profit/\(loss\)$",
    "share_of_jv_operating_loss": r"^share of joint venture operating loss$",
    "profit_disposal_players": r"^profit on disposal of player registrations$",
    "result_before_finance": r"^profit/\(loss\) before net finance charges$",
    "net_finance_charges": r"^net finance charges$",
    "result_before_tax": r"^\(loss\) before taxation$",
    "tax": r"^tax on loss$",
    "net_result": r"^\(loss\) for the financial year$",
}
CROSS_ROWS = tuple(PNL_ROWS)[:8]
# La tabla de la pág. 23, de las cabeceras a "(Loss) for the financial year". Con la página
# entera, el OCR solo lee 16 de sus cifras; con esta región, todas.
PNL_REGION = (0.10, 0.15, 0.99, 0.50)
TURNOVER_ROWS = {
    "gate": r"^gate and other match day revenues$",
    "broadcasting": r"^broadcasting$",
    "commercial": r"^commercial$",
    "property": r"^property$",
    "player_trading": r"^player trading$",
}
OPEX_ROWS = {
    "amortisation": r"^amortisation of player registrations$",
    "impairment": r"^impairment of player registrations \(see note 2\)$",
    "depreciation": r"^depreciation and impairment charges \(less amortisation of grants\)$",
    "dai_total": r"^total depreciation, amortisation and impairment$",
    "staff": r"^staff costs \(see note 6\)$",
    "other": r"^other operating charges$",
    "total": r"^total operating expenses$",
}
MIX = mix.for_club("arsenal")
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
}

GROUP_COMPANY = ("group_2025", "group_2024", "company_2025", "company_2024")
GROUP = ("group_2025", "group_2024")
BALANCE_ROWS = {
    "cash": r"^cash at bank and in hand\b",
    # El OCR lee «due within one year» como «du rithin one yea».
    "creditors_current": r"^creditors amounts falling du.*ithin one yea",
    "creditors_noncurrent": r"^creditors amounts falling due after more than one yea",
}
CREDITORS_CURRENT = {
    "trade": r"^trade creditors$", "tax": r"^other tax and social security$",
    "group": r"^amounts due to group undertakings$", "other": r"^other creditors$",
    "accruals": r"^accruals and deferred income$",
}
# «Amounts due to group undertakings» solo tiene cifra en la sociedad: en el grupo es un guion.
CREDITORS_CURRENT_LINES = tuple(CREDITORS_CURRENT)
CREDITORS_NONCURRENT = {
    "parent": r"^balance due to parent undertaking$", "debentures": r"^debenture loans$",
    "other": r"^other creditors$", "grants": r"^grants$",
    "accruals": r"^accruals and deferred income$",
}
BORROWINGS_NOTE = (
    "Balance due to parent undertaking (340.076: un préstamo de KSE UK Inc., reembolsable con "
    "dos años de preaviso, nota 16) más las debenture loans (18.218). La nota 16 llama «total "
    "debt» solo a las debentures. A menos de un año no hay deuda financiera: 0, derivado de la "
    "nota 15 (el total menos todas sus líneas del grupo)."
)
LEASE_NOTE = (
    "0, derivado: las notas 15 y 16 no tienen pasivos por arrendamiento (el total de cada una "
    "menos todas sus líneas del grupo). " + balance.FRS102_LEASES
)
TRANSFER_SPLIT_GAP = (
    "no se publica: las notas 13 y 15 dan el saldo por traspasos en una sola cifra, dentro de "
    "other debtors y other creditors a menos y a más de un año"
)

SPEC = ClubSpec(
    club_id="arsenal",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 23 y 34, vistas en la página renderizada. El OCR "
               "lee la £ como €, $, 2 o ·: la moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 23, PNL_COLUMNS, PNL_ROWS, region=PNL_REGION,
                sums=(
                    Sum("group_turnover", ("turnover_including_jv", "share_of_jv_turnover")),
                    Sum("operating_result", ("group_turnover", "operating_expenses")),
                    Sum("result_before_finance", ("operating_result",
                                                  "share_of_jv_operating_loss",
                                                  "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_finance", "net_finance_charges"),
                        TOTALS),
                    Sum("net_result", ("result_before_tax", "tax"), TOTALS),
                ),
                cross=(
                    Cross("total_2025", ("operations_2025", "players_2025"), CROSS_ROWS),
                    Cross("total_2024", ("operations_2024", "players_2024"), CROSS_ROWS),
                ),
            ),
            TableSpec(
                "staff", 34, ("2025", "2024"), STAFF_ROWS,
                select=r"^wages and salaries$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
            TableSpec(
                "turnover", 32, ("2025", "2024"), TURNOVER_ROWS, select=TURNOVER_ROWS["gate"],
                totals_after={"total": "player_trading"},
                sums=(Sum("total", tuple(TURNOVER_ROWS)),),
            ),
            TableSpec(
                "opex", 33, ("2025", "2024"), OPEX_ROWS, select=OPEX_ROWS["amortisation"],
                sums=(Sum("dai_total", ("amortisation", "impairment", "depreciation"), ("2025",)),
                      Sum("total", ("dai_total", "staff", "other"))),
            ),
            # Fase 3b: balance y notas 15 y 16.
            TableSpec("bs", 24, GROUP_COMPANY, BALANCE_ROWS),
            TableSpec("creditors_current", 39, GROUP_COMPANY, CREDITORS_CURRENT,
                      select=r"^trade creditors$", totals_after={"total": "accruals"},
                      sums=(Sum("total", CREDITORS_CURRENT_LINES, GROUP),)),
            TableSpec("creditors_noncurrent", 39, GROUP_COMPANY, CREDITORS_NONCURRENT,
                      select=r"^balance due to parent undertaking$",
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT), GROUP),)),
        ),
        links=(
            Link(("turnover", "total", "2025"), ("pnl", "group_turnover", "total_2025")),
            # El player trading de la nota 3 es la columna de traspasos de la cuenta.
            Link(("turnover", "player_trading", "2025"), ("pnl", "group_turnover", "players_2025")),
            Link(("opex", "total", "2025"), ("pnl", "operating_expenses", "total_2025"), sign=-1),
            MIX.check(),
            # Cada nota de acreedores es su línea del balance, que va en negativo.
            *(Link((note, "total", column), ("bs", line, column), sign=-1)
              for note, line in (("creditors_current", "creditors_current"),
                                 ("creditors_noncurrent", "creditors_noncurrent"))
              for column in GROUP),
        ),
        sentences=(
            SentenceFigureSpec(
                "transfer_receivables", 38, "Other debtors ... in respect of player transfers",
                r"include £(?P<amount>\d+\.\d) million in respect of player transfers "
                r"\(2024 - £38\.5 million\)", "group_2025", unit="hundred_thousands", decimals=1,
                note="Other debtors, a menos y a más de un año, incluyen 86,2 millones por "
                     "traspasos de jugadores (nota 13): la cifra, en millones con un decimal, "
                     "queda en centenas de miles de libras."),
            SentenceFigureSpec(
                "transfer_payables", 39, "Other creditors ... in respect of player transfers",
                r"include £(?P<amount>\d+\.\d) million \(2024 - £267\.8 million\) in respect",
                "group_2025", unit="hundred_thousands", decimals=1,
                note="Other creditors de las notas 15 y 16 incluyen 210,8 millones por traspasos "
                     "de jugadores: la cifra, en millones con un decimal, queda en centenas de "
                     "miles de libras."),
        ),
        gaps={**MIX.gaps(), **balance.split_gaps("transfer_payables", TRANSFER_SPLIT_GAP),
              **balance.split_gaps("transfer_receivables", TRANSFER_SPLIT_GAP)},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "group_turnover"),), "total_2025",
                       note="Incluye 454 de player trading (sobre todo cesiones), en la columna "
                            "de traspasos."),
            FigureSpec("revenue_ex_player_trading",
                       (Part("pnl", "group_turnover"),
                        Part("pnl", "group_turnover", "players_2025", sign=-1)),
                       "total_2025",
                       note="Group turnover total menos su columna de player trading (454, sobre "
                            "todo cesiones). Regla de la sección 9 del plan."),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("opex", "amortisation"),), "2025",
                       note="Amortisation of player registrations (nota 4)."),
            FigureSpec("impairment_player_registrations", (("opex", "impairment"),), "2025",
                       note="Impairment of player registrations (nota 4), excepcional según la "
                            "nota 2."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "total_2025", note="Profit on disposal of player registrations."),
            FigureSpec("player_trading_other_income", (("turnover", "player_trading"),), "2025",
                       note="Player trading de la nota 3: sobre todo cesiones (nota de la pág. 23; "
                            "el informe estratégico, pág. 4, da 0,5 millones de cesiones). Fuera "
                            "de los ingresos sin traspasos."),
            # Balance al 31/05/2025, columna del grupo.
            FigureSpec("cash", (("bs", "cash"),), "group_2025",
                       note="Cash at bank and in hand (pág. 24, nota 14)."),
            FigureSpec("borrowings_current",
                       (Part("creditors_current", "total"),
                        *(Part("creditors_current", line, sign=-1)
                          for line in CREDITORS_CURRENT_LINES)),
                       "group_2025", note=BORROWINGS_NOTE, expect_zero=True),
            FigureSpec("borrowings_non_current",
                       (("creditors_noncurrent", "parent"), ("creditors_noncurrent", "debentures")),
                       "group_2025", note=BORROWINGS_NOTE),
            FigureSpec("borrowings",
                       (("creditors_noncurrent", "parent"), ("creditors_noncurrent", "debentures")),
                       "group_2025", note=BORROWINGS_NOTE),
            *balance.zero_from_lines(
                "lease_liabilities",
                (("creditors_current", "total", CREDITORS_CURRENT_LINES),
                 ("creditors_noncurrent", "total", tuple(CREDITORS_NONCURRENT))),
                "group_2025", LEASE_NOTE),
        ),
    ),
)
