"""Celtic plc, 2024/25: informe anual de la web del club, con texto.

Texto directo con pdfplumber, sin OCR. Cada página del PDF son dos del informe, así que cada
tabla se lee en su mitad. Páginas localizadas buscando los títulos en el texto:
- pág. 26, mitad izquierda: Consolidated statement of comprehensive income, 2025 y 2024 en £000.
- pág. 33, mitad izquierda: nota 9, Staff particulars, tabla del grupo (Group), en £000.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)

LEFT_HALF = (0.0, 0.0, 0.5, 1.0)
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
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
}

REVENUE_EX_NOTE = (
    "La nota 5 (pág. 32) desglosa los ingresos en football and stadium operations, "
    "merchandising y multimedia and other commercial activities: no hay traspasos ni "
    "cesiones."
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
                "staff", 33, COLUMNS, STAFF_ROWS, region=LEFT_HALF,
                header_label=r"^group$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
        ),
    ),
)
