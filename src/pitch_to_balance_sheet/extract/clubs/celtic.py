"""Celtic plc, 2024/25: informe anual de la web del club, con texto.

Texto directo con pdfplumber, sin OCR. Cada página del PDF son dos del informe, así que cada
tabla se lee en su mitad. Páginas localizadas buscando los títulos en el texto:
- pág. 26, mitad izquierda: Consolidated statement of comprehensive income, 2025 y 2024 en £000.
- pág. 33, mitad izquierda: nota 9, Staff particulars, tabla del grupo (Group), en £000; y nota
  8, Exceptional operating (expenses)/income, con los acuerdos por rescisión de contratos de
  trabajo (staff_costs_exceptional). Su total tiene que coincidir con la línea de la cuenta.

Fase 3b, balance al 30/06/2025:
- pág. 26, mitad derecha: Consolidated balance sheet.
- pág. 38, mitad izquierda: nota 25 (borrowings) y nota 26 (trade and other payables, con los
  arrendamientos), que cuadran con el balance.
- pág. 37, mitad derecha: nota 23, acciones emitidas por clase, en miles de acciones.
Celtic no separa los saldos por traspasos: van dentro de trade receivables y trade and other
payables (notas 21 y 26).
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

LEFT_HALF = (0.0, 0.0, 0.5, 1.0)
RIGHT_HALF = (0.5, 0.0, 1.0, 1.0)
COLUMNS = ("2025", "2024")
PNL_ROWS = {
    "revenue": r"^revenue$",
    # "Operating expenses" va en una línea y sus cifras en la siguiente, que es esta.
    "operating_expenses": r"^\(before intangible asset transactions and exceptional items\)$",
    "trading_profit": r"^profit from trading before intangible asset transactions and "
                      r"exceptional items$",
    "exceptional_items": r"^exceptional operating \(expense\)/income$",
    "amortisation": r"^amortisation of intangible assets$",
    "profit_disposal_intangibles": r"^profit on disposal of intangible assets$",
    "operating_profit": r"^operating profit$",
    "finance_income": r"^finance income$",
    "finance_expense": r"^finance expense$",
    "result_before_tax": r"^profit before tax$",
    "tax": r"^tax expense$",
    "net_result": r"^profit and total comprehensive profit for the year$",
}
EXCEPTIONAL_ROWS = {
    "impairment": r"^impairment of intangible assets and other prepaid costs$",
    "player_salaries_compensation": r"^compensation for player salaries$",
    "contract_termination": r"^settlement agreements on unforeseen contract termination$",
}
EXCEPTIONAL_NOTE = (
    "Settlement agreements on unforeseen contract termination (nota 8): costes por rescindir "
    "contratos de trabajo, que el club presenta como partida excepcional. La nota no dice si "
    "están también en los gastos de personal de la nota 9."
)
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
}

REVENUE_ROWS = {
    "ticketing": r"^ticketing$",
    "commercial_sponsorship": r"^commercial/sponsorship$",
    "retail": r"^retail outlets and e-commerce$",
    "media": r"^media rights$",
    "stadium": r"^stadium operations$",
    "other": r"^other$",
}
INTANGIBLE_ROWS = {
    "opening": r"^at 1 july$",
    "charge": r"^charge for year$",
    "impairment": r"^provision for impairment$",
    "disposals": r"^disposals$",
    "closing": r"^at 30 june$",
}
MIX = mix.for_club("celtic")
REVENUE_EX_NOTE = (
    "La nota 5 (pág. 32) desglosa los ingresos en football and stadium operations, "
    "merchandising y multimedia and other commercial activities: no hay traspasos ni "
    "cesiones."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
)


CURRENT_ASSETS = {"inventories": r"^inventories$",
                  "receivables": r"^trade and other receivables$",
                  "cash": r"^cash and cash equivalents$"}
NONCURRENT_LIABILITIES = {
    "ccps_debt": r"^debt element of convertible cumulative preference shares$",
    "payables": r"^trade and other payables$",
    "leases": r"^lease liabilities$",
    "provisions": r"^provisions$",
    "deferred_tax": r"^deferred tax liabilities$",
}
CURRENT_LIABILITIES = {
    "payables": r"^trade and other payables$",
    "leases": r"^lease liabilities$",
    "borrowings": r"^borrowings$",
    "provisions": r"^provisions$",
    "deferred_income": r"^deferred income$",
}
PAYABLES_COLUMNS = ("group_2025", "group_2024", "company_2025", "company_2024")
SHARE_COLUMNS = ("authorised_2025", "authorised_2024", "issued_2025", "issued_2024")
SHARE_ROWS = {
    "ordinary": r"^ordinary shares of 1p each\b",
    "deferred": r"^deferred shares of 1p each\b",
    "cpo": r"^convertible preferred ordinary shares of 1 each\b",
    "ccps": r"^60p each\b",  # "Convertible Cumulative Preference Shares of" va en la línea anterior
    "total": r"^27,214 27,197$",  # la fila del total: el rótulo son las cifras en £000
}
BORROWINGS_NOTE = (
    "Borrowings corrientes (96: «other current borrowings», sin interés, según la nota 25) más "
    "el elemento de deuda de las Convertible Cumulative Preference Shares (4.129, no corriente): "
    "un pasivo financiero a coste amortizado (NIC 32, nota 23)."
)
TRANSFER_GAP = (
    "no se publica: Celtic no separa los saldos por traspasos, que van dentro de trade "
    "receivables y de trade and other payables (notas 21 y 26); la nota 29 solo da el número de "
    "jugadores con importes contingentes"
)
SHARES_NOTE = (
    "Ordinary Shares de 1p emitidas al 30/06/2025 (nota 23), en miles de acciones: la clase que "
    "cotiza y la de las ganancias por acción básicas. Quedan fuera las Deferred Shares (sin "
    "derechos económicos), las Convertible Preferred Ordinary Shares (12.655 miles) y las "
    "Convertible Cumulative Preference Shares (15.627 miles), convertibles en ordinarias. El "
    "informe no menciona acciones propias."
)

SPEC = ClubSpec(
    club_id="celtic",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 26 y 33, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£000",
        tables=(
            TableSpec(
                "pnl", 26, COLUMNS, PNL_ROWS, region=LEFT_HALF,
                sums=(
                    Sum("trading_profit", ("revenue", "operating_expenses")),
                    Sum("operating_profit", ("trading_profit", "exceptional_items",
                                             "amortisation", "profit_disposal_intangibles")),
                    Sum("result_before_tax", ("operating_profit", "finance_income",
                                              "finance_expense")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "exceptional", 33, COLUMNS, EXCEPTIONAL_ROWS, region=LEFT_HALF,
                select=r"^settlement agreements",
                totals_after={"exceptional_total": "contract_termination"},
                sums=(Sum("exceptional_total", tuple(EXCEPTIONAL_ROWS)),),
            ),
            TableSpec(
                "staff", 33, COLUMNS, STAFF_ROWS, region=LEFT_HALF,
                header_label=r"^group$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
            TableSpec(
                "revenue", 32, COLUMNS, REVENUE_ROWS, region=LEFT_HALF, select=r"^ticketing$",
                totals_after={"total": "other"},
                sums=(Sum("total", tuple(REVENUE_ROWS)),),
            ),
            TableSpec(
                # Nota 17, bloque de amortización: los intangibles son derechos de jugadores.
                "intangibles", 35, COLUMNS, INTANGIBLE_ROWS, region=RIGHT_HALF,
                select=INTANGIBLE_ROWS["charge"], block=(r"^amortisation$", r"^at 30 june$"),
                sums=(Sum("closing", ("opening", "charge", "impairment", "disposals")),),
            ),
            # Fase 3b: balance y notas.
            TableSpec("bs_current_assets", 26, COLUMNS, CURRENT_ASSETS, region=RIGHT_HALF,
                      totals_after={"total": "cash"},
                      block=(r"^current assets$", r"^total assets$"),
                      sums=(Sum("total", tuple(CURRENT_ASSETS)),)),
            TableSpec("bs_noncurrent_liabilities", 26, COLUMNS, NONCURRENT_LIABILITIES,
                      region=RIGHT_HALF, totals_after={"total": "deferred_tax"},
                      block=(r"^non-current liabilities$", r"^current liabilities$"),
                      sums=(Sum("total", tuple(NONCURRENT_LIABILITIES)),)),
            TableSpec("bs_current_liabilities", 26, COLUMNS, CURRENT_LIABILITIES,
                      region=RIGHT_HALF, totals_after={"total": "deferred_income"},
                      block=(r"^current liabilities$", r"^total liabilities$"),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)),)),
            TableSpec("borrowings_note", 38, COLUMNS,
                      {"borrowings": r"^other current borrowings$"}, region=LEFT_HALF,
                      select=r"^other current borrowings$"),
            TableSpec("payables_current", 38, PAYABLES_COLUMNS,
                      {"accrued": r"^accrued expenses$", "payables": r"^trade and other payables$",
                       "leases": r"^leasehold liabilities$", "tax": r"^corporation tax$",
                       "group": r"^amounts owing to group companies$"},
                      region=LEFT_HALF, select=r"^accrued expenses$",
                      totals_after={"total": "group"},
                      sums=(Sum("total", ("accrued", "payables", "leases", "tax", "group")),)),
            TableSpec("share_capital", 37, SHARE_COLUMNS, SHARE_ROWS, region=RIGHT_HALF,
                      header=r"^No\.[’']000$", block=(r"^equity$", SHARE_ROWS["total"]),
                      sums=(Sum("total", ("ordinary", "deferred", "cpo", "ccps")),)),
        ),
        links=(
            *(Link(("exceptional", "exceptional_total", year), ("pnl", "exceptional_items", year))
              for year in COLUMNS),
            *(Link(("revenue", "total", year), ("pnl", "revenue", year)) for year in COLUMNS),
            *(Link(("intangibles", "charge", year), ("pnl", "amortisation", year), sign=-1)
              for year in COLUMNS),
            MIX.check(),
            # Balance: las notas 25 y 26 son sus líneas del balance (la 26 suma los arrendamientos
            # a trade and other payables).
            *(Link(("borrowings_note", "borrowings", year),
                   ("bs_current_liabilities", "borrowings", year)) for year in COLUMNS),
            *(Link(("payables_current", "leases", f"group_{year}"),
                   ("bs_current_liabilities", "leases", year)) for year in COLUMNS),
            *(LinkSum(("bs_current_liabilities", "payables", year),
                      tuple(("payables_current", row, f"group_{year}")
                            for row in ("accrued", "payables", "tax", "group")))
              for year in COLUMNS),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
              **balance.gaps("transfer_payables", TRANSFER_GAP),
              **balance.gaps("transfer_receivables", TRANSFER_GAP)},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("staff_costs_exceptional", (("exceptional", "contract_termination"),),
                       "2025", note=EXCEPTIONAL_NOTE, negate=True,
                       included_in_staff_costs="dudoso"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("intangibles", "charge"),), "2025",
                       note="Charge for year de la nota 17 (intangibles: derechos de jugadores)."),
            FigureSpec("impairment_player_registrations", (("intangibles", "impairment"),),
                       "2025", note="Provision for impairment de la nota 17: la parte de "
                                   "jugadores de los 2,004 de la nota 8; el resto son otros "
                                   "gastos anticipados."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_intangibles"),),
                       "2025", note="Profit on disposal of intangible assets: los intangibles "
                                    "son derechos de jugadores (nota 17)."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Cash and cash equivalents (pág. 26, nota 22)."),
            *balance.split("borrowings", Part("bs_current_liabilities", "borrowings"),
                           Part("bs_noncurrent_liabilities", "ccps_debt"), "2025",
                           note=BORROWINGS_NOTE),
            *balance.split("lease_liabilities", Part("bs_current_liabilities", "leases"),
                           Part("bs_noncurrent_liabilities", "leases"), "2025",
                           note="Lease liabilities del balance (pág. 26; nota 29: 721 en total)."),
            FigureSpec("shares_outstanding", (Part("share_capital", "ordinary", "issued_2025"),),
                       "2025", note=SHARES_NOTE, unit="thousand_shares"),
        ),
    ),
)
