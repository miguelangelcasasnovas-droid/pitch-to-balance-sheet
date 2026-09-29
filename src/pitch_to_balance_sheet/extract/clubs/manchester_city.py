"""Manchester City Football Club Limited, 2024/25: PDF digital del club, descargado a mano.

Texto directo con pdfplumber, sin OCR. Páginas localizadas buscando los títulos en el texto:
- pág. 20, Statement of Profit or Loss: cuatro columnas en £000 (operaciones sin traspasos 2025,
  traspasos y amortización 2025, total 2025 y total 2024).
- pág. 37, nota 7, Employees: "aggregate payroll costs", 2025 y 2024 en £000. El total incluye
  los pagos basados en acciones.
- pág. 35, nota 4, Revenue: las partidas de ingresos (mapeo en config/line_items.yaml).
- pág. 42, nota 12, Intangible fixed assets: el cargo del año de los derechos de jugadores. La
  nota no separa amortización y deterioro: la nota 5 (pág. 36) lo llama "Amortisation and
  impairment of intangible assets".

Fase 3b, balance a 30/06/2025 (pág. 22) y sus notas:
- pág. 46, nota 16: receivables arising from player transfers, corrientes y no corrientes.
- pág. 47, notas 17 y 18: acreedores corrientes y no corrientes, con los arrendamientos y los
  payables arising from player transfers.
- pág. 48, nota 19: el total de los arrendamientos.
Deuda financiera: el importe a más de un año con City Football Group USA LLC (nota 18), que
tiene fecha de devolución (julio de 2030); los importes con el grupo a menos de un año son
refacturaciones sin interés (nota 17) y van aparte, en related_party_financing (decisión del
usuario del 29/09/2026).
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
    LinkSum,
    Part,
    Sum,
    TableSpec,
)

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025", "total_2024")
PNL_ROWS = {
    "revenue": r"^revenue$",
    "other_operating_income": r"^other operating income$",
    "operating_expenses": r"^operating expenses$",
    "operating_loss": r"^operating loss$",
    "profit_disposal_players": r"^profit on disposal of players registrations$",
    "result_before_interest": r"^profit before interest and taxation$",
    "interest_receivable": r"^interest receivable and similar income$",
    "interest_payable": r"^interest payable and similar charges$",
    "result_before_tax": r"^\(loss\)/profit on ordinary activities before taxation$",
    "tax": r"^taxation$",
    "net_result": r"^\(loss\)/profit on ordinary activities after taxation$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
    "share_based_payments": r"^share-based payments$",
    "staff_costs_total": r"^total$",
}

REVENUE_ROWS = {
    "matchday": r"^matchday$",
    "broadcasting_uefa": r"^broadcasting - uefa$",
    "broadcasting_other": r"^broadcasting - all other$",
    "other_commercial": r"^other commercial activities$",
    "total": r"^total$",
}
INTANGIBLE_ROWS = {"charge": r"^charge in the year$"}
MIX = mix.for_club("manchester_city")
AMORTISATION_NOTE = (
    "Charge in the year de Players' registrations (nota 12). Incluye el deterioro, si lo hay: la "
    "nota 5 (pág. 36) lo llama «Amortisation and impairment» y la nota 12 no lo separa."
)
REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 20) separa la columna de traspasos y amortización, y en "
    "Revenue esa columna es un guion: no hay traspasos ni cesiones."
)

YEARS = ("2025", "2024")
CURRENT_LIABILITIES = {"derivatives": r"^derivative financial instruments$",
                       "payables": r"^trade and other payables$",
                       "deferred_income": r"^deferred income$"}
RECEIVABLES_CURRENT = {
    "trade": r"^trade receivables$",
    "transfers": r"^receivables arising from player transfers$",
    "group": r"^amounts owed by group undertakings$",
    "related": r"^amounts owed by related party undertakings",
    "other": r"^other receivables including tax",
    "prepayments": r"^prepayments and accrued income$",
    "total": r"^total$",
}
PAYABLES_CURRENT = {
    "lease": r"^lease liabilities \(note 19\)$",
    "trade": r"^trade payables$",
    "transfers": r"^payables arising from player transfers$",
    "group": r"^amounts owed to group undertakings$",
    "related": r"^amounts owed to related party undertakings",
    "other": r"^other payables including tax",
    "accruals": r"^accruals$",
    "total": r"^total$",
}
PAYABLES_NON_CURRENT = {
    "lease": r"^lease liabilities \(note 19\)$",
    "transfers": r"^payables arising from player transfers$",
    "group": r"^amounts owed to group undertakings$",
    "total": r"^total$",
}
LEASE_MATURITY = {
    "within_one_year": r"^within one year$",
    "one_to_two": r"^between one and two years$",
    "two_to_five": r"^between two and five years$",
    "after_five": r"^after more than five years$",
    "total": r"^total$",
}
BORROWINGS_NOTE = (
    "A menos de un año, 0, derivado: el pasivo corriente del balance (pág. 22) menos todas sus "
    "líneas, sin deuda financiera. A más de un año, los «Amounts owed to group undertakings» de "
    "la nota 18 (pág. 47): «are owed to City Football Group USA LLC by the Company. These "
    "balances are due in July 2030». Tienen fecha de devolución, así que son deuda financiera, "
    "como los préstamos de KSE a Arsenal y de FSG a Liverpool (decisión del usuario del "
    "29/09/2026). La nota no dice si devengan interés."
)
RELATED_NOTE = (
    "Amounts owed to group undertakings a menos de un año (nota 17, pág. 47): «are primarily "
    "recharges for head office costs by other subsidiaries within the Group. These balances are "
    "due within one year and no interest is charged on the outstanding amounts». Sin interés ni "
    "calendario de devolución: fuera de borrowings, solo para la variante de sensibilidad. El "
    "club tiene además 366.927 a cobrar de sociedades del grupo (nota 16), también sin interés."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
)


SPEC = ClubSpec(
    club_id="manchester_city",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 20 y 37, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£000",
        tables=(
            TableSpec(
                "pnl", 20, PNL_COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_loss", ("revenue", "other_operating_income",
                                           "operating_expenses")),
                    Sum("result_before_interest", ("operating_loss", "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_interest", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
                cross=(Cross("total_2025", ("operations_2025", "players_2025"),
                             tuple(PNL_ROWS)),),
            ),
            TableSpec(
                "staff", 37, ("2025", "2024"), STAFF_ROWS,
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)[:-1]),),
            ),
            TableSpec(
                "revenue", 35, ("2025", "2024"), REVENUE_ROWS,
                sums=(Sum("total", tuple(REVENUE_ROWS)[:-1]),),
            ),
            TableSpec(
                "intangibles", 42, ("other", "players", "total"), INTANGIBLE_ROWS,
                cross=(Cross("total", ("other", "players"), ("charge",)),),
            ),
            # Fase 3b: balance y notas.
            TableSpec("bs_noncurrent_assets", 22, YEARS,
                      {"receivables": r"^trade and other receivables$"},
                      block=(r"^non-current assets$", r"^trade and other receivables$")),
            TableSpec("bs_current_assets", 22, YEARS,
                      {"receivables": r"^trade and other receivables$",
                       "cash": r"^cash at bank and in hand$"},
                      totals_after={"total": "cash"},
                      block=(r"^current assets$", r"^current liabilities$"),
                      sums=(Sum("total", ("receivables", "cash")),)),
            TableSpec("bs_current_liabilities", 22, YEARS, CURRENT_LIABILITIES,
                      totals_after={"total": "deferred_income"},
                      block=(r"^current liabilities$", r"^net current"),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)),)),
            TableSpec("bs_noncurrent_liabilities", 22, YEARS,
                      {"payables": r"^trade and other payables$"},
                      totals_after={"total": "payables"},
                      block=(r"^non-current liabilities$", r"^net assets$"),
                      sums=(Sum("total", ("payables",)),)),
            TableSpec("receivables_current", 46, YEARS, RECEIVABLES_CURRENT,
                      block=(r"^current trade and other receivables$", r"^total$"),
                      sums=(Sum("total", tuple(RECEIVABLES_CURRENT)[:-1]),)),
            TableSpec("receivables_noncurrent", 46, YEARS,
                      {"transfers": r"^receivables arising from player transfers$",
                       "total": r"^total$"},
                      block=(r"^non-current trade and other receivables$", r"^total$"),
                      sums=(Sum("total", ("transfers",)),)),
            TableSpec("payables_current", 47, YEARS, PAYABLES_CURRENT, select=r"^accruals$",
                      sums=(Sum("total", tuple(PAYABLES_CURRENT)[:-1]),)),
            TableSpec("payables_noncurrent", 47, YEARS, PAYABLES_NON_CURRENT,
                      select=r"^amounts owed to group undertakings due after one year",
                      sums=(Sum("total", tuple(PAYABLES_NON_CURRENT)[:-1]),)),
            TableSpec("leases", 48, YEARS, LEASE_MATURITY,
                      select=r"^maturity of lease liabilities$",
                      sums=(Sum("total", tuple(LEASE_MATURITY)[:-1]),)),
        ),
        links=(
            Link(("revenue", "total", "2025"), ("pnl", "revenue", "total_2025")),
            Link(("revenue", "total", "2024"), ("pnl", "revenue", "total_2024")),
            # El cargo de la nota 12 es la columna de traspasos y amortización de la cuenta.
            Link(("intangibles", "charge", "total"), ("pnl", "operating_expenses", "players_2025"),
                 sign=-1),
            MIX.check(),
            # Balance: cada nota es su línea del balance (en negativo en el pasivo).
            Link(("receivables_current", "total", "2025"),
                 ("bs_current_assets", "receivables", "2025")),
            Link(("receivables_noncurrent", "total", "2025"),
                 ("bs_noncurrent_assets", "receivables", "2025")),
            Link(("payables_current", "total", "2025"),
                 ("bs_current_liabilities", "payables", "2025"), sign=-1),
            Link(("payables_noncurrent", "total", "2025"),
                 ("bs_noncurrent_liabilities", "payables", "2025"), sign=-1),
            LinkSum(("leases", "total", "2025"), (("payables_current", "lease", "2025"),
                                                  ("payables_noncurrent", "lease", "2025"))),
            Link(("leases", "within_one_year", "2025"), ("payables_current", "lease", "2025")),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025",
                       note="Incluye 531 de pagos basados en acciones."),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "charge", "players"),), "2025", note=AMORTISATION_NOTE),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "total_2025", note="Profit on disposal of players' registrations."),
            # Balance a 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Cash at bank and in hand (pág. 22)."),
            FigureSpec("borrowings_current",
                       (Part("bs_current_liabilities", "total"),
                        *(Part("bs_current_liabilities", line, sign=-1)
                          for line in CURRENT_LIABILITIES)),
                       "2025", note=BORROWINGS_NOTE, expect_zero=True),
            FigureSpec("borrowings_non_current", (("payables_noncurrent", "group"),), "2025",
                       note=BORROWINGS_NOTE),
            FigureSpec("borrowings", (("payables_noncurrent", "group"),), "2025",
                       note=BORROWINGS_NOTE),
            FigureSpec("related_party_financing", (("payables_current", "group"),), "2025",
                       note=RELATED_NOTE),
            *balance.split("lease_liabilities", Part("payables_current", "lease"),
                           Part("payables_noncurrent", "lease"), "2025",
                           total=Part("leases", "total"),
                           note="Lease liabilities de las notas 17 y 18; el total, de la nota 19 "
                                "(arrendamiento del Etihad Stadium, nota 14)."),
            *balance.split("transfer_payables", Part("payables_current", "transfers"),
                           Part("payables_noncurrent", "transfers"), "2025",
                           note="Payables arising from player transfers (notas 17 y 18)."),
            *balance.split("transfer_receivables", Part("receivables_current", "transfers"),
                           Part("receivables_noncurrent", "transfers"), "2025",
                           note="Receivables arising from player transfers (nota 16)."),
        ),
        gaps={
            **MIX.gaps(),
            "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
            "impairment_player_registrations": (
                "no se publica por separado: la nota 12 (pág. 42) da un solo cargo del año, "
                "169,546, que la nota 5 (pág. 36) llama «Amortisation and impairment of "
                "intangible assets»; va entero en amortisation_player_registrations"),
        },
    ),
)
