"""Borussia Dortmund GmbH & Co. KGaA, 2024/25: cuentas IFRS de grupo.

Decisión del usuario del 27/09/2026: el Geschäftsbericht en alemán (vinculante) es la fuente y
el informe en inglés, el control; las cifras tienen que coincidir. El PDF alemán lo descargó el
usuario a mano de aktie.bvb.de/publikationen/geschaftsberichte, porque la página lo carga desde
una API con token.

Los dos informes traen las cuentas consolidadas IFRS del grupo (desde la pág. 124) y las
individuales HGB de la KGaA (desde la pág. 198); se usan las IFRS de grupo. Texto directo con
pdfplumber, y la misma paginación en las dos versiones:
- pág. 126, Konzerngesamtergebnisrechnung / Consolidated statement of comprehensive income, en
  TEUR / EUR '000, 2024/2025 y 2023/2024. Los negativos llevan signo menos ("-27.359"); en el
  alemán, los miles se separan con punto.
- pág. 161, nota 20, Personalaufwand / Personnel expenses, en positivo; su total tiene que
  coincidir con la línea de la cuenta de resultados, cambiada de signo.
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
REVENUE_EX_NOTE = (
    "La nota 16 (pág. 160) desglosa los ingresos en Spielbetrieb, Werbung, TV-Vermarktung, "
    "Merchandising y Conference, Catering, Sonstige; los traspasos van aparte, en Ergebnis aus "
    "Transfergeschäften (nota 17): no hay traspasos ni cesiones en los ingresos."
)


def document(language: str, control_index: int | None) -> DocumentSpec:
    german = language == "de"
    pnl_rows = {
        "revenue": r"^konzernumsatzerlose" if german else r"^consolidated revenue",
        "net_transfer_income": (r"^ergebnis aus transfergeschaften" if german
                                else r"^net transfer income"),
        "other_operating_income": (r"^sonstige betriebliche ertrage" if german
                                   else r"^other operating income"),
        "cost_of_materials": r"^materialaufwand" if german else r"^cost of materials",
        "personnel_expenses": r"^personalaufwand" if german else r"^personnel expenses",
        "depreciation": (r"^abschreibungen" if german
                         else r"^depreciation, amortisation and write-downs"),
        "other_operating_expenses": (r"^sonstige betriebliche aufwendungen" if german
                                     else r"^other operating expenses"),
        "operating_result": (r"^ergebnis der geschaftstatigkeit$" if german
                             else r"^result from operating activities$"),
        "associates": (r"^ergebnis aus beteiligungen an assoziierten unternehmen" if german
                       else r"^net income/loss from investments in associates"),
        "finance_income": r"^finanzierungsertrage" if german else r"^finance income",
        "finance_costs": r"^finanzierungsaufwendungen" if german else r"^finance costs",
        "financial_result": r"^finanzergebnis$" if german else r"^financial result$",
        "result_before_tax": (r"^ergebnis vor ertragsteuern$" if german
                              else r"^profit before income taxes$"),
        "income_taxes": r"^ertragsteuern" if german else r"^income taxes",
        "net_result": (r"^konzernjahresuberschuss$" if german
                       else r"^consolidated net profit for the year$"),
    }
    staff_rows = {
        "wages_and_salaries": r"^lohne und gehalter$" if german else r"^wages and salaries$",
        "social_security": (r"^sozialversicherungsabgaben$" if german
                            else r"^social security contributions$"),
    }
    return DocumentSpec(
        method="text",
        unit_evidence=r"in TEUR" if german else r"EUR '000",
        thousands="." if german else ",",
        control_index=control_index,
        tables=(
            TableSpec(
                "pnl", 126, YEARS, pnl_rows, header=HEADER,
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
                "staff", 161, YEARS, staff_rows, header=HEADER,
                select=staff_rows["wages_and_salaries"],
                totals_after={"staff_costs_total": "social_security"},
                sums=(Sum("staff_costs_total", tuple(staff_rows)),),
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
    )


SPEC = ClubSpec(
    club_id="borussia_dortmund",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«in TEUR» en las págs. 126 y 161 del Geschäftsbericht en alemán («EUR '000» en "
               "el inglés), en el texto del PDF.",
    primary=document("de", None),
    controls=(document("en", 0),),
)
