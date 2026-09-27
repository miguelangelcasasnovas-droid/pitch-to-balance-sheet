"""Borussia Dortmund GmbH & Co. KGaA, 2024/25: cuentas IFRS de grupo.

Decisión del usuario del 27/09/2026: el Geschäftsbericht en alemán (vinculante) es la fuente y
el informe en inglés, el control; las cifras tienen que coincidir. El PDF alemán no tiene URL
pública localizable (la página de informes lo carga desde una API con token): hay que
descargarlo a mano. Hasta entonces el club queda en error. Lo de abajo describe la versión
inglesa, que es el control.

El informe trae las cuentas consolidadas IFRS del grupo (desde la pág. 124) y las individuales
HGB de la KGaA (desde la pág. 198); se usan las IFRS de grupo. Texto directo con pdfplumber.
Páginas localizadas buscando los títulos en el texto:
- pág. 126, Consolidated statement of comprehensive income, en EUR '000, 2024/2025 y 2023/2024.
  Los negativos llevan signo menos ("-27,359").
- pág. 161, nota 20, Personnel expenses, en positivo; su total tiene que coincidir con la línea
  de la cuenta de resultados, cambiada de signo.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    Sum,
    TableSpec,
)

YEARS = ("2025", "2024")
HEADER = r"^\d{4}/\d{4}$"
PNL_ROWS = {
    "revenue": r"^consolidated revenue",
    "net_transfer_income": r"^net transfer income",
    "other_operating_income": r"^other operating income",
    "cost_of_materials": r"^cost of materials",
    "personnel_expenses": r"^personnel expenses",
    "depreciation": r"^depreciation, amortisation and write-downs",
    "other_operating_expenses": r"^other operating expenses",
    "operating_result": r"^result from operating activities$",
    "associates": r"^net income/loss from investments in associates",
    "finance_income": r"^finance income",
    "finance_costs": r"^finance costs",
    "financial_result": r"^financial result$",
    "result_before_tax": r"^profit before income taxes$",
    "income_taxes": r"^income taxes",
    "net_result": r"^consolidated net profit for the year$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security": r"^social security contributions$",
}
REVENUE_EX_NOTE = (
    "La nota 16 (pág. 160) desglosa los ingresos en match operations, advertising, TV "
    "marketing, merchandising y conference, catering, miscellaneous; los traspasos van aparte, "
    "en net transfer income (nota 17): no hay traspasos ni cesiones en los ingresos."
)

GERMAN_PENDING = (
    "falta la especificación del Geschäftsbericht en alemán: se escribe (páginas y rótulos en "
    "alemán) cuando el PDF esté en data/raw/manual/borussia_dortmund_2024-25_de.pdf"
)

SPEC = ClubSpec(
    club_id="borussia_dortmund",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«EUR '000» en las págs. 126 y 161 del informe en inglés, en el texto del PDF.",
    primary=DocumentSpec(method="text", tables=(), figures=(), unit_evidence="",
                         pending=GERMAN_PENDING),
    controls=(DocumentSpec(
        method="text",
        unit_evidence=r"EUR '000",
        control_index=0,
        tables=(
            TableSpec(
                "pnl", 126, YEARS, PNL_ROWS, header=HEADER,
                sums=(
                    Sum("operating_result", ("revenue", "net_transfer_income",
                                             "other_operating_income", "cost_of_materials",
                                             "personnel_expenses", "depreciation",
                                             "other_operating_expenses")),
                    Sum("financial_result", ("associates", "finance_income", "finance_costs")),
                    Sum("result_before_tax", ("operating_result", "financial_result")),
                    Sum("net_result", ("result_before_tax", "income_taxes")),
                ),
            ),
            TableSpec(
                "staff", 161, YEARS, STAFF_ROWS, header=HEADER,
                select=r"^wages and salaries$",
                totals_after={"staff_costs_total": "social_security"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        links=tuple(Link(("staff", "staff_costs_total", year), ("pnl", "personnel_expenses", year),
                         sign=-1) for year in YEARS),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
        ),
    ),),
)
