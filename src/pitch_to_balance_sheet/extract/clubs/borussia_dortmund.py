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
El resultado atribuible a la matriz ("- Eigenkapitalgebern der Muttergesellschaft:") aparece dos
veces en la pág. 126, para el resultado neto y para el global: se toma la fila que va justo
después de "vom Konzernjahresüberschuss zuzurechnen:".

Fase 3a, en los dos idiomas:
- pág. 160, notas 16 (Umsatzerlöse / Revenue, partidas de ingresos; mapeo en
  config/line_items.yaml) y 17 (Ergebnis aus Transfergeschäften / Net transfer income).
- pág. 150, cuadro de intangibles: el bloque de amortizaciones de 2024/25, columna Spielerwerte.
- pág. 155, nota 8, en una frase: las außerplanmäßige Wertminderungen / impairment losses de
  los jugadores reclasificados como mantenidos para la venta, que van dentro de las
  amortizaciones de la cuenta.
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
    SentenceFigureSpec,
    Sum,
    TableSpec,
)

YEARS = ("2025", "2024")
HEADER = r"^\d{4}/\d{4}$"
MIX = mix.for_club("borussia_dortmund")
DISPOSALS_NOTE = (
    "Ergebnis aus Transfergeschäften (nota 17): Brutto-Transferentgelt menos Transferkosten y "
    "Restbuchwerte. Es la línea de la cuenta de resultados."
)
IMPAIRMENT_NOTE = (
    "Nota 8 (pág. 155): außerplanmäßige Wertminderungen de los intangibles reclasificados como "
    "mantenidos para la venta (jugadores que se van a traspasar), incluidas en las "
    "amortizaciones de la cuenta. Cuadra: 85.396 + 145 + 7.000 = 92.541, frente a los 92.542 de "
    "amortización de intangibles de la nota 21."
)
ATTRIBUTABLE_NOTE = (
    "vom Konzernjahresüberschuss zuzurechnen: Eigenkapitalgebern der Muttergesellschaft (pág. "
    "126): todo el resultado; no hay minoritarios. Informativa."
)
REVENUE_EX_NOTE = (
    "La nota 16 (pág. 160) desglosa los ingresos en Spielbetrieb, Werbung, TV-Vermarktung, "
    "Merchandising y Conference, Catering, Sonstige; los traspasos van aparte, en Ergebnis aus "
    "Transfergeschäften (nota 17). Pero según el informe de gestión (pág. 57), Conference, "
    "Catering, Sonstige incluye 3.858 de cesiones, derechos de formación y solidaridad FIFA: "
    "pendiente de decidir si se restan (no es una línea de las cuentas)."
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
        "attributable_parent": (r"eigenkapitalgebern der muttergesellschaft$" if german
                                else r"owners of the parent$"),
    }
    attributable_anchor = (r"^vom konzernjahresuberschuss zuzurechnen$" if german
                           else r"^consolidated net profit for the year attributable to$")
    revenue_rows = {
        "match_operations": r"^spielbetrieb$" if german else r"^match operations$",
        "advertising": r"^werbung$" if german else r"^advertising$",
        "tv": r"^tv-vermarktung$" if german else r"^tv marketing$",
        "merchandising": r"^merchandising$",
        "conference": (r"^conference, catering, sonstige$" if german
                       else r"^conference, catering, miscellaneous$"),
    }
    transfer_rows = {
        "gross": r"^brutto-transferentgelt$" if german else r"^gross transfer proceeds$",
        "costs": r"^transferkosten$" if german else r"^transfer costs$",
        "net": r"^netto-transferentgelt$" if german else r"^net transfer proceeds$",
        "carrying_amounts": (r"^restbuchwerte und sonstige ausbuchungen$" if german
                             else r"^residual carrying amounts and other derecognised items$"),
        "result": r"^ergebnis aus transfergeschaften$" if german else r"^net transfer income$",
    }
    intangible_rows = {
        "opening": r"^stand 30. juni 2024$" if german else r"^as at 30 june 2024$",
        "additions": r"^zugange$" if german else r"^additions$",
        "disposals": r"^abgange$" if german else r"^disposals$",
        "reclassification": (r"^umgliederung in als zur verausserung gehaltene vermogenswerte$"
                             if german else r"^reclassification to assets held for sale$"),
        "closing": r"^stand 30. juni 2025$" if german else r"^as at 30 june 2025$",
    }
    amortisation_block = ((r"^abschreibungen$" if german
                           else r"^depreciation, amortisation and write-downs$",
                           intangible_rows["closing"]),
                          (intangible_rows["opening"], intangible_rows["closing"]))
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
                after={"attributable_parent": attributable_anchor},
                sums=(
                    Sum("operating_result", ("revenue", "net_transfer_income",
                                             "other_operating_income", "cost_of_materials",
                                             "personnel_expenses", "depreciation",
                                             "other_operating_expenses")),
                    Sum("financial_result", ("associates", "finance_income", "finance_costs")),
                    Sum("result_before_tax", ("operating_result", "financial_result")),
                    Sum("net_result", ("result_before_tax", "income_taxes")),
                    Sum("net_result", ("attributable_parent",)),
                ),
            ),
            TableSpec(
                "staff", 161, YEARS, staff_rows, header=HEADER,
                select=staff_rows["wages_and_salaries"],
                totals_after={"staff_costs_total": "social_security"},
                sums=(Sum("staff_costs_total", tuple(staff_rows)),),
            ),
            TableSpec(
                "revenue", 160, YEARS, revenue_rows, header=HEADER,
                select=revenue_rows["match_operations"],
                totals_after={"total": "conference"},
                sums=(Sum("total", tuple(revenue_rows)),),
            ),
            TableSpec(
                "transfers", 160, YEARS, transfer_rows, header=HEADER,
                select=transfer_rows["gross"],
                sums=(Sum("net", ("gross", "costs")), Sum("result", ("net", "carrying_amounts"))),
            ),
            TableSpec(
                "intangibles", 150, ("players", "rights", "total"), intangible_rows,
                header=(r"^(Spielerwerte|Rechte|Summe)$" if german
                        else r"^(registrations|rights|Total)$"),
                block=amortisation_block,
                sums=(Sum("closing", ("opening", "additions", "-disposals",
                                      "reclassification")),),
                cross=(Cross("total", ("players", "rights"), tuple(intangible_rows)),),
            ),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "personnel_expenses", year),
                   sign=-1) for year in YEARS),
            *(Link(("revenue", "total", year), ("pnl", "revenue", year)) for year in YEARS),
            *(Link(("transfers", "result", year), ("pnl", "net_transfer_income", year))
              for year in YEARS),
            MIX.check(),
        ),
        sentences=(
            SentenceFigureSpec(
                "impairment_player_registrations", 155,
                "außerplanmäßige Wertminderungen" if german else "impairment losses",
                (r"^Wertminderungen in Höhe von TEUR (?P<amount>[\d.]+) \(Vorjahr TEUR 9\.986\)"
                 if german else r"impairment losses of EUR (?P<amount>[\d,]+) thousand "
                                r"\(previous year: EUR 9,986 thousand\)"),
                "2025", note=IMPAIRMENT_NOTE),
        ),
        gaps={**MIX.gaps(), "player_trading_other_income": PLAYER_OTHER_INCOME_GAP},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            FigureSpec("net_result_attributable_parent", (("pnl", "attributable_parent"),),
                       "2025", note=ATTRIBUTABLE_NOTE),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "additions", "players"),), "2025",
                       note="Zugänge del bloque de Abschreibungen, columna Spielerwerte (pág. "
                            "150): la amortización del año de los jugadores."),
            FigureSpec("profit_on_player_disposals", (("transfers", "result"),), "2025",
                       note=DISPOSALS_NOTE),
        ),
    )


PLAYER_OTHER_INCOME_GAP = (
    "pendiente de decidir: según el informe de gestión (pág. 57), los ingresos por cesiones, "
    "derechos de formación y solidaridad FIFA (3.858 miles) están dentro de la partida de "
    "ingresos «Conference, Catering, Sonstige», no fuera de ellos"
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
