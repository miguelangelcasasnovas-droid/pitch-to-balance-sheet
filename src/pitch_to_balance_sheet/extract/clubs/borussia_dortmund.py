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
- pág. 57, informe de gestión, en frases: el desglose de "Conference, Catering, Sonstige"
  (decisión del usuario del 28/09/2026). Las cesiones, derechos de formación y solidaridad FIFA
  (3.858) se restan de revenue_ex_player_trading y van a player_trading_other_income; la
  hospitality y el catering (22.052) y la preventa de entradas (5.086) van a matchday, y el
  resto de la línea, a commercial. Cuadres: el total de la frase es la línea de la nota 16, y
  Conference y Catering (27.237) es la hospitality y el catering más los eventos (5.186).

Fase 3b, balance al 30/06/2025, en los dos idiomas:
- pág. 125, Konzernbilanz / consolidated statement of financial position: activo corriente y
  pasivo no corriente y corriente, con sus totales sin rótulo.
- pág. 157: nota 11 (Finanzverbindlichkeiten), en una frase, y nota 12, el valor actual de los
  arrendamientos.
- notas 5 (pág. 154) y 13 (pág. 158), en frases: los saldos por traspasos dentro de los deudores
  y acreedores comerciales. El informe no los separa en corriente y no corriente.
- acciones: nota 9, las emitidas (pág. 155) y las propias (pág. 156 en alemán, 155 en inglés);
  cuadran con el número medio de acciones en circulación de la nota 26 (pág. 173), porque no
  cambió en el año.
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
    SentenceFigureSpec,
    Sum,
    TableSpec,
    TextCellSpec,
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
    "Konzernumsatzerlöse menos las cesiones, derechos de formación y solidaridad FIFA (3.858) que "
    "el informe de gestión (pág. 57) sitúa dentro de Conference, Catering, Sonstige. Los "
    "traspasos van aparte, en Ergebnis aus Transfergeschäften (nota 17). Regla de la sección 9."
)
BALANCE_HEADER = {"de": r"^30\.06\.20\d\d$", "en": r"^30/06/20\d\d$"}
BORROWINGS_NOTE = (
    "Finanzverbindlichkeiten (pág. 125): préstamos bancarios para inversiones en inmovilizado, "
    "con garantía (33.599 pendientes según la nota 11), y el valor negativo del swap de tipos de "
    "interés que los cubre (575), que la nota 11 incluye en la misma cifra."
)
TRANSFER_SPLIT_GAP = (
    "no se publica: las notas 5 y 13 dan el saldo por traspasos dentro de los deudores y "
    "acreedores comerciales, sin separar la parte corriente y la no corriente"
)
# clave -> (rótulo, página en alemán, patrón en alemán, página en inglés, patrón en inglés).
# Cada frase se localiza con la cifra del año anterior, salvo las de acciones, que no la traen.
BALANCE_CELLS = {
    "borrowings": ("Finanzverbindlichkeiten", 157,
                   r"Finanzverbindlichkeiten in Höhe von TEUR (?P<amount>[\d.]+) \(30\. Juni "
                   r"2024$", 157,
                   r"financial liabilities amounted to EUR (?P<amount>[\d,]+) thousand "
                   r"\(30 June 2024: EUR$"),
    "transfer_receivables": ("Transferforderungen", 154,
                             r"^TEUR (?P<amount>[\d.]+) \(30\. Juni 2024 TEUR 141\.682\) "
                             r"enthalten", 154,
                             r"included EUR (?P<amount>[\d,]+) thousand in transfer receivables "
                             r"\(30 June 2024: EUR 141,682"),
    "transfer_payables": ("Transferverbindlichkeiten", 158,
                          r"davon umfassen TEUR (?P<amount>[\d.]+) \(30\. Juni 2024 TEUR "
                          r"131\.406\)", 158,
                          r"^EUR (?P<amount>[\d,]+) thousand \(30 June 2024: EUR 131,406 "
                          r"thousand\) related to liabilities from transfer deals"),
    "shares_issued": ("Stückaktien", 155,
                      r"eingeteilt in (?P<amount>\d{1,3}(?:\.\d{3})+) Stückaktien", 155,
                      r"divided into (?P<amount>\d{1,3}(?:,\d{3})+) no-par value shares"),
    "treasury_shares": ("eigene Stückaktien", 156,
                        r"(?P<amount>\d{1,3}(?:\.\d{3})*) Stückaktien im eigenen", 155,
                        r"consisted of (?P<amount>\d{1,3}(?:,\d{3})*) no"),
    "average_shares": ("gewichteter Durchschnitt der umlaufenden Aktien", 173,
                       r"2024/2025 (?P<amount>\d{1,3}(?:\.\d{3})+) Stück \(Vorjahr "
                       r"110\.377\.320 Stück\)", 173,
                       r"2024/2025 amounted to (?P<amount>\d{1,3}(?:,\d{3})+) \(previous year: "
                       r"110,377,320\)"),
}
SHARES_NOTE = (
    "Acciones emitidas (110.396.220, nota 9) menos acciones propias (18.900): una sola clase. "
    "Cuadra con el número medio de acciones en circulación de la nota 26, que no cambió en el "
    "año."
)

REPORT_CELLS = {  # clave -> (rótulo, patrón en alemán, patrón en inglés), pág. 57
    "line_total": ("Conference, Catering, Sonstige",
                   r"^TEUR (?P<amount>[\d.]+) \(Vorjahr TEUR 56\.004\) – eine Reduktion",
                   r"to EUR (?P<amount>[\d,]+) thousand\. This also"),
    "conference_catering": ("Conference und Catering",
                            r"lag mit TEUR (?P<amount>[\d.]+) um TEUR 1\.228 unter",
                            r"previous year to EUR (?P<amount>[\d,]+) thousand\. Borussia"),
    "hospitality": ("Hospitality Catering und Public Catering",
                    r"sanken um TEUR 1\.493 auf TEUR (?P<amount>[\d.]+) \(Vorjahr",
                    r"declined by EUR 1,493 thousand to EUR (?P<amount>[\d,]+) thousand"),
    "events": ("Veranstaltungen außerhalb des Spielbetriebes und Stadiontouren",
               r"um TEUR 265 auf TEUR (?P<amount>[\d.]+) \(Vorjahr TEUR 4\.921\)",
               r"^(?P<amount>[\d,]+) thousand \(previous year: EUR 4,921 thousand\)"),
    "presale": ("Vorverkaufsgebühren und Porto",
                r"Erlöse in Höhe von TEUR (?P<amount>[\d.]+) \(Vorjahr TEUR 4\.852\)",
                r"generated income of EUR (?P<amount>[\d,]+)$"),
    "loans": ("Erlöse aus Leihgeschäften, Ausbildungsentschädigungen, FIFA-Solidarität",
              r"beliefen sich auf TEUR (?P<amount>[\d.]+) \(Vorjahr",
              r"year on year to EUR (?P<amount>[\d,]+) thousand \(previous year: EUR 1,671"),
}


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
    balance_header = BALANCE_HEADER[language]
    current_assets = {
        "inventories": r"^vorrate$" if german else r"^inventories$",
        "receivables": (r"^forderungen aus lieferungen und leistungen und sonstige" if german
                        else r"^trade and other financial receivables$"),
        "cash": (r"^zahlungsmittel und zahlungsmittelaquivalente$" if german
                 else r"^cash and cash equivalents$"),
        "prepaid": r"^aktive rechnungsabgrenzungsposten$" if german else r"^prepaid expenses$",
        "held_for_sale": (r"^zur verausserung gehaltene vermogenswerte$" if german
                          else r"^assets held for sale$"),
    }
    noncurrent_liabilities = {
        "provisions": r"^ruckstellungen$" if german else r"^provisions$",
        "borrowings": r"^finanzverbindlichkeiten$" if german else r"^financial liabilities$",
        "leases": r"^verbindlichkeiten aus leasing$" if german else r"^lease liabilities$",
        "trade": (r"^verbindlichkeiten aus lieferungen und leistungen$" if german
                  else r"^trade payables$"),
        "other": (r"^sonstige finanzielle verbindlichkeiten$" if german
                  else r"^other financial liabilities$"),
    }
    current_liabilities = {
        **noncurrent_liabilities,
        "tax": r"^steuerschulden$" if german else r"^tax liabilities$",
        "deferred_income": (r"^passive rechnungsabgrenzungsposten$" if german
                            else r"^deferred income$"),
    }
    lease_rows = {
        "within_one_year": r"^bis zu 1 jahr$" if german else r"^less than 1 year$",
        "one_to_five": (r"^nach mehr als 1 jahr und bis zu 5 jahre$" if german
                        else r"^between 1 and 5 years$"),
        "after_five": r"^mehr als 5 jahre$" if german else r"^more than 5 years$",
        "finance_costs": (r"^kunftige finanzierungskosten aus leasing$" if german
                          else r"^future finance charges from leases$"),
        "present_value": (r"^barwert der verbindlichkeiten aus leasing$" if german
                          else r"^present value of liabilities from leases$"),
    }
    footer = r"^geschaftsbericht 2024/2025" if german else r"^annual report 2024/2025"
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
            # Fase 3b: balance y nota 12.
            TableSpec("bs_current_assets", 125, YEARS, current_assets, header=balance_header,
                      totals_after={"total": "held_for_sale"},
                      block=(r"^kurzfristige vermogenswerte$" if german else r"^current assets$",
                             r"^passiva$" if german else r"^equity and liabilities$"),
                      sums=(Sum("total", tuple(current_assets)),)),
            TableSpec("bs_noncurrent_liabilities", 125, YEARS, noncurrent_liabilities,
                      header=balance_header, totals_after={"total": "other"},
                      block=(r"^langfristige schulden$" if german
                             else r"^non-current liabilities$",
                             r"^kurzfristige schulden$" if german else r"^current liabilities$"),
                      sums=(Sum("total", tuple(noncurrent_liabilities)),)),
            TableSpec("bs_current_liabilities", 125, YEARS, current_liabilities,
                      header=balance_header, totals_after={"total": "deferred_income"},
                      block=(r"^kurzfristige schulden$" if german else r"^current liabilities$",
                             footer),
                      sums=(Sum("total", tuple(current_liabilities)),)),
            TableSpec("leases", 157, YEARS, lease_rows, header=balance_header,
                      totals_after={"undiscounted": "after_five"},
                      select=lease_rows["present_value"],
                      sums=(Sum("undiscounted", ("within_one_year", "one_to_five", "after_five")),
                            Sum("present_value", ("undiscounted", "-finance_costs")))),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "personnel_expenses", year),
                   sign=-1) for year in YEARS),
            *(Link(("revenue", "total", year), ("pnl", "revenue", year)) for year in YEARS),
            *(Link(("transfers", "result", year), ("pnl", "net_transfer_income", year))
              for year in YEARS),
            # Las frases del informe de gestión hablan de la misma línea, y sus partes cuadran.
            Link(("report", "line_total", "2025"), ("revenue", "conference", "2025")),
            LinkSum(("report", "conference_catering", "2025"),
                    (("report", "hospitality", "2025"), ("report", "events", "2025"))),
            MIX.check(),
            # Balance: la frase de la nota 11 y el valor actual de la nota 12 son la suma de sus
            # líneas del balance; y las acciones en circulación, el número medio de la nota 26.
            LinkSum(("borrowings_note", "borrowings", "2025"),
                    (("bs_noncurrent_liabilities", "borrowings", "2025"),
                     ("bs_current_liabilities", "borrowings", "2025"))),
            *(LinkSum(("leases", "present_value", year),
                      (("bs_noncurrent_liabilities", "leases", year),
                       ("bs_current_liabilities", "leases", year))) for year in YEARS),
            LinkSum(("average_shares", "average_shares", "2025"),
                    (("shares_issued", "shares_issued", "2025"),
                     ("treasury_shares", "treasury_shares", "2025")), signs=(1, -1)),
        ),
        text_cells=(
            *(TextCellSpec("report", key, 57, label, german_pattern if german
                           else english_pattern)
              for key, (label, german_pattern, english_pattern) in REPORT_CELLS.items()),
            # Cada frase de balance en su propia tabla: están en páginas distintas.
            *(TextCellSpec(f"{key}_note" if key in ("borrowings", "transfer_receivables",
                                                    "transfer_payables") else key,
                           key, german_page if german else english_page, label,
                           german_pattern if german else english_pattern)
              for key, (label, german_page, german_pattern, english_page, english_pattern)
              in BALANCE_CELLS.items()),
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
        gaps={**MIX.gaps(), **balance.split_gaps("transfer_payables", TRANSFER_SPLIT_GAP),
              **balance.split_gaps("transfer_receivables", TRANSFER_SPLIT_GAP)},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading",
                       (Part("pnl", "revenue"), Part("report", "loans", sign=-1)), "2025",
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
            FigureSpec("player_trading_other_income", (("report", "loans"),), "2025",
                       note="Erlöse aus Leihgeschäften, Ausbildungsentschädigungen und dem "
                            "FIFA-Solidaritätsmechanismus (informe de gestión, pág. 57): dentro "
                            "de Conference, Catering, Sonstige, restados de los ingresos sin "
                            "traspasos."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Zahlungsmittel und Zahlungsmitteläquivalente (pág. 125, nota 7)."),
            *balance.split("borrowings", Part("bs_current_liabilities", "borrowings"),
                           Part("bs_noncurrent_liabilities", "borrowings"), "2025",
                           total=Part("borrowings_note", "borrowings"), note=BORROWINGS_NOTE),
            *balance.split("lease_liabilities", Part("bs_current_liabilities", "leases"),
                           Part("bs_noncurrent_liabilities", "leases"), "2025",
                           total=Part("leases", "present_value"),
                           note="Verbindlichkeiten aus Leasing (pág. 125); el total, el Barwert "
                                "de la nota 12."),
            FigureSpec("transfer_payables",
                       (("transfer_payables_note", "transfer_payables"),), "2025",
                       note="Transferverbindlichkeiten dentro de los acreedores comerciales "
                            "(nota 13, pág. 158)."),
            FigureSpec("transfer_receivables",
                       (("transfer_receivables_note", "transfer_receivables"),), "2025",
                       note="Transferforderungen dentro de los deudores comerciales (nota 5, "
                            "pág. 154)."),
            FigureSpec("shares_outstanding",
                       (Part("shares_issued", "shares_issued"),
                        Part("treasury_shares", "treasury_shares", sign=-1)),
                       "2025", note=SHARES_NOTE, unit="shares"),
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
