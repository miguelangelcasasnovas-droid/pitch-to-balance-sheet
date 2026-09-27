"""AFC Ajax NV, 2024/25: jaarverslag, en neerlandés, cuentas consolidadas. Con texto.

Texto directo con pdfplumber. Las cifras van en miles de euros ("BEDRAGEN x EUR 1.000"), con
punto de miles y negativos entre paréntesis. Páginas localizadas buscando los títulos:
- pág. 81, Geconsolideerde winst-en-verliesrekening, 2024/2025 y 2023/2024. Varios rótulos
  ocupan dos líneas y tres acaban en "resultaat vergoedingssommen", así que las filas con cifras
  se identifican por su orden, con anclas; los cuadres comprueban que cada cifra está en su fila.
- pág. 110, nota 27, lonen, salarissen en sociale lasten, en positivo; su total tiene que
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
PNL_ORDER = (
    "revenue",  # Netto-omzet
    "cost_of_sales",  # Inkoopwaarde omzet
    "wages",  # Lonen, salarissen en sociale lasten
    "depreciation",  # Afschrijvingen op vaste activa
    "other_expenses",  # Overige bedrijfskosten
    "result_before_player_amortisation",  # Bedrijfsresultaat vóór afschrijvingen en resultaat...
    "player_amortisation",  # Afschrijvingen vergoedingssommen
    "transfer_result",  # Resultaat vergoedingssommen
    "operating_result",  # Bedrijfsresultaat na afschrijvingen en resultaat vergoedingssommen
    "associates",  # Waardeverandering deelnemingen
    "financial_income",  # Financiële baten
    "financial_expenses",  # Financiële lasten
    "securities",  # Waardeverandering effecten
    "result_before_tax",  # Resultaat uit bedrijfsuitoefening vóór belastingen
    "tax",  # Belastingen resultaat uit bedrijfsuitoefening
    "net_result",  # Resultaat uit bedrijfsuitoefening na belastingen
    "attributable",  # Toe te rekenen aan de aandeelhouders van de vennootschap
)
PNL_ANCHORS = {
    "revenue": r"^netto-omzet",
    "wages": r"^lonen, salarissen en sociale lasten",
    "transfer_result": r"^resultaat vergoedingssommen$",
    "tax": r"^belastingen resultaat uit bedrijfsuitoefening",
    "attributable": r"vennootschap$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^lonen en salarissen$",
    "social_charges": r"^sociale lasten$",
    "pension_charges": r"^pensioenlasten$",
}
ATTRIBUTABLE_NOTE = (
    "Toe te rekenen aan de aandeelhouders van de vennootschap (pág. 81): todo el resultado; no "
    "hay minoritarios. Informativa."
)
REVENUE_EX_NOTE = (
    "La nota 25 (pág. 108) desglosa la netto-omzet en ingresos de partidos y competiciones, "
    "partnerships, televisie, merchandising y overige baten; los traspasos van aparte, en "
    "resultaat vergoedingssommen: no hay traspasos ni cesiones en los ingresos."
)

SPEC = ClubSpec(
    club_id="ajax",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«BEDRAGEN x EUR 1.000» en las págs. 81 y 110, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"BEDRAGEN x EUR 1\.000",
        thousands=".",
        tables=(
            TableSpec(
                "pnl", 81, YEARS, {}, header=HEADER,
                rows_by_order=PNL_ORDER, anchors=PNL_ANCHORS,
                sums=(
                    Sum("result_before_player_amortisation", ("revenue", "cost_of_sales", "wages",
                                                              "depreciation", "other_expenses")),
                    Sum("operating_result", ("result_before_player_amortisation",
                                             "player_amortisation", "transfer_result")),
                    Sum("result_before_tax", ("operating_result", "associates",
                                              "financial_income", "financial_expenses",
                                              "securities")),
                    Sum("net_result", ("result_before_tax", "tax")),
                    Sum("attributable", ("net_result",)),
                ),
            ),
            TableSpec(
                "staff", 110, YEARS, STAFF_ROWS, header=HEADER,
                select=r"^lonen en salarissen$",
                totals_after={"staff_costs_total": "pension_charges"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        links=tuple(Link(("staff", "staff_costs_total", year), ("pnl", "wages", year), sign=-1)
                    for year in YEARS),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            FigureSpec("net_result_attributable_parent", (("pnl", "attributable"),), "2025",
                       note=ATTRIBUTABLE_NOTE),
        ),
    ),
)
