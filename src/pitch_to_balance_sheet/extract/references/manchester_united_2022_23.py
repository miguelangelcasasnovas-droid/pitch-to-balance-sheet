"""Manchester United plc, Form 20-F del ejercicio 2022/23 (cerrado el 30/06/2023), con texto.
Ejercicio de referencia de la compra de INEOS (anuncio del 24/12/2023). Las cuentas están en
libras (£'000).

Páginas localizadas buscando los títulos en el texto:
- pág. 108 (F-6), Consolidated statement of profit or loss: 2023, 2022 y 2021.
- pág. 123 (F-21), nota 4.1, ingresos: commercial, broadcasting y matchday, con el total sin
  rótulo. No hay traspasos: el resultado por venta de registros va en su línea de la cuenta.
- págs. 110 y 111 (F-8 y F-9), Consolidated balance sheet.
- pág. 143 (F-41), nota 22, en frases: acciones de clase A y B emitidas al 30/06/2023 y acciones
  de clase A en autocartera. La portada del 20-F da 54.537,360 acciones de clase A «as of the
  close of the period», que es la cifra de 2022 de la nota; se usa la nota, como en 2024/25
  (docs/incoherencias-fuentes.md).
- pág. 164, firmas: «Date: 27 October 2023».
"""

from pitch_to_balance_sheet.extract import balance
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    Part,
    Sum,
    TableSpec,
    TextCellSpec,
)

COLUMNS = ("2023", "2022", "2021")
BALANCE_COLUMNS = COLUMNS[:2]
PNL_ROWS = {
    "revenue": r"^revenue from contracts with customers$",
    "operating_expenses": r"^operating expenses$",
    "other_operating_income": r"^other operating income$",
    "profit_disposal_intangibles": r"^profit on disposal of intangible assets$",
    "operating_result": r"^operating loss$",
    "finance_costs": r"^finance costs$",
    "finance_income": r"^finance income$",
    "net_finance": r"^net finance \(costs\)/income$",
    "result_before_tax": r"^loss before income tax$",
    "tax": r"^income tax credit/\(expense\)$",
    "net_result": r"^loss for the year$",
}
REVENUE_ROWS = {
    "sponsorship": r"^sponsorship$",
    "retail": r"^retail, merchandising, apparel & products licensing revenue$",
    "commercial": r"^commercial$",
    "domestic": r"^domestic competitions$",
    "european": r"^european competitions$",
    "broadcasting_other": r"^other$",
    "broadcasting": r"^broadcasting$",
    "matchday": r"^matchday$",
}
NONCURRENT_LIABILITIES = {
    "deferred_tax": r"^deferred tax liabilities$",
    "deferred_revenue": r"^contract liabilities - deferred revenue( 4\.2)?$",
    "payables": r"^trade and other payables$", "borrowings": r"^borrowings$",
    "leases": r"^lease liabilities$", "derivatives": r"^derivative financial instruments$",
    "provisions": r"^provisions$",
}
CURRENT_LIABILITIES = {
    "deferred_revenue": r"^contract liabilities - deferred revenue( 4\.2)?$",
    "payables": r"^trade and other payables$", "borrowings": r"^borrowings$",
    "leases": r"^lease liabilities$", "derivatives": r"^derivative financial instruments$",
    "provisions": r"^provisions$",
}
CURRENT_ASSETS = {
    "inventories": r"^inventories$", "prepayments": r"^prepayments$",
    "accrued_revenue": r"^contract assets accrued revenue( 4\.2)?$",
    "trade": r"^trade receivables$", "other": r"^other receivables$",
    "tax": r"^income tax receivable$", "derivatives": r"^derivative financial instruments$",
    "cash": r"^cash and cash equivalents$",
}
SHARES_PAGE = 143
SHARES = {
    "class_a": (r"comprised (?P<amount>[\d,]+) \(2022: 54,537,360\) Class A",
                "Class A ordinary shares"),
    "class_b": (r"^(?P<amount>[\d,]+) \(2022: 110,207,613\) Class B",
                "Class B ordinary shares"),
    "treasury": (r"(?P<amount>[\d,]+) Class A ordinary shares are currently held in treasury",
                 "Class A ordinary shares held in treasury"),
}

REVENUE_EX_NOTE = (
    "La nota 4.1 (pág. 123) desglosa los ingresos en commercial, broadcasting y matchday: no hay "
    "traspasos ni cesiones; el resultado por venta de registros va en su línea de la cuenta "
    "(pág. 108)."
)
SHARES_NOTE = (
    "Acciones de clase A y B emitidas al 30/06/2023 (nota 22, pág. 143) menos las 1.682.896 de "
    "clase A en autocartera. Las de clase B no cotizan, pero tienen los mismos derechos "
    "económicos que las A. La portada del 20-F da 54.537.360 clase A, la cifra de 2022."
)

SPEC = ClubSpec(
    club_id="manchester_united",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las cuentas del 20-F, en el texto del PDF. La acción cotiza "
               "en USD; las cuentas, en libras.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£.000",
        tables=(
            TableSpec(
                "pnl", 108, COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_result", ("revenue", "operating_expenses",
                                             "other_operating_income",
                                             "profit_disposal_intangibles")),
                    Sum("net_finance", ("finance_costs", "finance_income")),
                    Sum("result_before_tax", ("operating_result", "net_finance")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "revenue", 123, COLUMNS, REVENUE_ROWS,
                totals_after={"total": "matchday"},
                sums=(
                    Sum("commercial", ("sponsorship", "retail")),
                    Sum("broadcasting", ("domestic", "european", "broadcasting_other")),
                    Sum("total", ("commercial", "broadcasting", "matchday")),
                ),
            ),
            TableSpec("bs_current_assets", 110, BALANCE_COLUMNS, CURRENT_ASSETS,
                      totals_after={"total": "cash"},
                      block=(r"^current assets$", r"^total assets$"),
                      sums=(Sum("total", tuple(CURRENT_ASSETS)),)),
            TableSpec("bs_noncurrent_liabilities", 111, BALANCE_COLUMNS,
                      NONCURRENT_LIABILITIES, totals_after={"total": "provisions"},
                      block=(r"^non-current liabilities$", r"^current liabilities$"),
                      sums=(Sum("total", tuple(NONCURRENT_LIABILITIES)),)),
            TableSpec("bs_current_liabilities", 111, BALANCE_COLUMNS,
                      CURRENT_LIABILITIES, totals_after={"total": "provisions"},
                      block=(r"^current liabilities$", r"^total equity and liabilities$"),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)),)),
        ),
        text_cells=tuple(
            TextCellSpec("shares", key, SHARES_PAGE, label, pattern, column="2023")
            for key, (pattern, label) in SHARES.items()),
        links=tuple(Link(("revenue", "total", year), ("pnl", "revenue", year))
                    for year in COLUMNS),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2023"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2023",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2023",
                       note="Cash and cash equivalents (balance, nota 21)."),
            *balance.split("borrowings", Part("bs_current_liabilities", "borrowings"),
                           Part("bs_noncurrent_liabilities", "borrowings"), "2023",
                           note="Borrowings del balance (nota 25): préstamos y bonos (senior "
                                "secured notes) y la línea de crédito revolving."),
            FigureSpec("shares_outstanding",
                       (Part("shares", "class_a"), Part("shares", "class_b"),
                        Part("shares", "treasury", sign=-1)), "2023", unit="shares",
                       note=SHARES_NOTE),
        ),
    ),
)
