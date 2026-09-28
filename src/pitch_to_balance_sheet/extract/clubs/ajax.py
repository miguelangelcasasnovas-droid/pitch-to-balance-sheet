"""AFC Ajax NV, 2024/25: jaarverslag, en neerlandés, cuentas consolidadas. Con texto.

Texto directo con pdfplumber. Las cifras van en miles de euros ("BEDRAGEN x EUR 1.000"), con
punto de miles y negativos entre paréntesis. Páginas localizadas buscando los títulos:
- pág. 81, Geconsolideerde winst-en-verliesrekening, 2024/2025 y 2023/2024. Varios rótulos
  ocupan dos líneas y tres acaban en "resultaat vergoedingssommen", así que las filas con cifras
  se identifican por su orden, con anclas; los cuadres comprueban que cada cifra está en su fila.
- pág. 110, nota 27, lonen, salarissen en sociale lasten, en positivo; su total tiene que
  coincidir con la línea de la cuenta de resultados, cambiada de signo.
- pág. 108, nota 25, netto-omzet: las partidas de ingresos, con un subtotal de partidos y
  competiciones (mapeo en config/line_items.yaml).
Amortización y resultado de traspasos son líneas de la cuenta (notas 30 y 31, págs. 112-113).

Fase 3b, balance al 30/06/2025 (pág. 80). En el balance, las partidas con nota llevan su cifra en
una columna interior sin cabecera, que no se puede leer como celda; se leen los subtotales del
balance y cada partida en su nota:
- pág. 97, nota 6: los deudores a más de un año (columna Debiteuren, eindbalans).
- pág. 98, nota 8: los debiteuren inzake vergoedingssommen, a menos de un año.
- pág. 104, notas 18 y 19: impuestos diferidos y arrendamientos.
- pág. 105, notas 20 y 21: crediteuren inzake vergoedingssommen, a más y a menos de un año.
- pág. 106, notas 22, 23 y 24.
Ajax no tiene deuda financiera: la línea de crédito estaba sin disponer (pág. 85) y las notas de
todas las líneas del pasivo suman sus subtotales del balance, sin ningún préstamo.
- pág. 115: el número medio de acciones en circulación, que es el del cierre porque el capital
  no cambió en el año (pág. 102).
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    Part,
    SentenceFigureSpec,
    Sum,
    TableSpec,
)

YEARS = ("2025", "2024")
HEADER = r"^\d{4}/\d{4}$"
BALANCE_HEADER = r"^20\d\d$"  # «30 juni 2025»: el año es la palabra que se alinea
BORROWINGS_NOTE = (
    "0, derivado: el balance (pág. 80) no tiene deuda financiera y la línea de crédito bancaria "
    "estaba sin disponer al cierre (pág. 85). El subtotal de cada bloque del pasivo menos las "
    "notas de todas sus líneas (18 a 24; la nota 22 sin la vennootschapsbelasting, que el "
    "balance lleva al activo) es 0."
)
NOTE6_COLUMNS = ("loan", "debtors", "signing_fees", "total")
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
REVENUE_ROWS = {
    "competition": r"^recettes competitie, nationale beker en vriendschappelijke wedstrijden$",
    "european_receipts": r"^recettes europese competities$",
    "european_prizes": r"^premies europese competities$",
    "season_tickets": r"^seizoenkaarten$",
    "business_seats": r"^business-seats en skybox-plaatsen$",
    "indirect": r"^indirecte wedstrijdbaten$",
    "subtotal": r"^subtotaal$",
    "partnerships": r"^partnerships$",
    "television": r"^televisie$",
    "merchandising": r"^merchandising$",
    "other": r"^overige baten$",
    "total": r"^totaal netto-omzet$",
}
MATCH_ROWS = ("competition", "european_receipts", "european_prizes", "season_tickets",
              "business_seats", "indirect")
MIX = mix.for_club("ajax")
REVENUE_EX_NOTE = (
    "La nota 25 (pág. 108) desglosa la netto-omzet en ingresos de partidos y competiciones, "
    "partnerships, televisie, merchandising y overige baten; los traspasos van aparte, en "
    "resultaat vergoedingssommen: no hay traspasos ni cesiones en los ingresos."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals (resultaat vergoedingssommen es el "
    "neto de ventas, nota 31)"
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
            TableSpec(
                "revenue", 108, YEARS, REVENUE_ROWS, header=HEADER,
                sums=(Sum("subtotal", MATCH_ROWS),
                      Sum("total", ("subtotal", "partnerships", "television", "merchandising",
                                    "other"))),
            ),
            # Fase 3b: balance y notas.
            TableSpec("bs_assets", 80, YEARS, {"cash": r"^liquide middelen$"},
                      header=BALANCE_HEADER, region=(0.0, 0.0, 0.5, 1.0)),
            TableSpec("bs_noncurrent_liabilities", 80, YEARS,
                      {"other": r"^overige schulden \(20\)"}, header=BALANCE_HEADER,
                      region=(0.5, 0.0, 1.0, 1.0), totals_after={"total": "other"},
                      block=(r"^langlopende verplichtingen$", r"^kortlopende verplichtingen$")),
            TableSpec("bs_current_liabilities", 80, YEARS,
                      {"accruals": r"^overlopende passiva \(24\)"}, header=BALANCE_HEADER,
                      region=(0.5, 0.0, 1.0, 1.0), totals_after={"total": "accruals"},
                      block=(r"^kortlopende verplichtingen$", r"^totaal passiva$")),
            TableSpec("note6", 97, NOTE6_COLUMNS,
                      {"opening": r"^beginbalans\b", "additions": r"^toevoeging\b",
                       "fair_value": r"^reele waarde aanpassing\b",
                       "receipts": r"^ontvangsten\b",
                       "to_current": r"^opgenomen onder kortlopende vorderingen\b",
                       "closing": r"^eindbalans\b"},
                      header=r"^(nv|debiteuren|tekengelden|totaal)$",
                      block=(r"^2024/2025$", r"^eindbalans\b"),
                      sums=(Sum("closing", ("opening", "additions", "fair_value", "receipts",
                                            "to_current"), columns=("debtors",)),)),
            TableSpec("note8", 98, YEARS,
                      {"transfers": r"^debiteuren inzake vergoedingssommen$",
                       "other": r"^overige debiteuren$", "provision": r"^voorziening debiteuren$"},
                      header=BALANCE_HEADER, select=r"^overige debiteuren$",
                      totals_after={"total": "provision"},
                      sums=(Sum("total", ("transfers", "other", "provision")),)),
            TableSpec("note18", 104, YEARS, {"closing": r"^eindbalans$"}, header=HEADER,
                      select=r"^tariefswijziging$"),
            TableSpec("note19", 104, YEARS,
                      {"payments": r"^leasebetalingen$",
                       "current": r"^opgenomen onder kortlopende verplichtingen$",
                       "closing": r"^eindbalans$"},
                      header=HEADER, select=r"^leasebetalingen$",
                      totals_after={"total": "payments"},
                      sums=(Sum("closing", ("total", "current")),)),
            TableSpec("note20", 105, YEARS, {}, header=BALANCE_HEADER,
                      select=r"^overige schulden$", rows_by_order=("transfers", "other", "total"),
                      anchors={"transfers": r"^crediteuren inzake vergoedingssommen$"},
                      sums=(Sum("total", ("transfers", "other")),)),
            TableSpec("note21", 105, YEARS,
                      {"transfers": r"^crediteuren inzake vergoedingssommen$",
                       "other": r"^overige crediteuren$"},
                      header=BALANCE_HEADER, select=r"^overige crediteuren$",
                      totals_after={"total": "other"},
                      sums=(Sum("total", ("transfers", "other")),)),
            TableSpec("note22", 106, YEARS,
                      {"wage_tax": r"^loonbelasting$", "vat": r"^omzetbelasting$",
                       "corporate_tax": r"^vennootschapsbelasting$",
                       "social_security": r"^premies sociale verzekeringen$"},
                      header=BALANCE_HEADER, select=r"^loonbelasting$",
                      totals_after={"total": "social_security"},
                      sums=(Sum("total", ("wage_tax", "vat", "corporate_tax",
                                          "social_security")),)),
            TableSpec("note23", 106, YEARS, {}, header=BALANCE_HEADER,
                      select=r"^deze post bevat onder andere te betalen transferkosten",
                      rows_by_order=("other", "total"), sums=(Sum("total", ("other",)),)),
            TableSpec("note24", 106, YEARS, {}, header=BALANCE_HEADER,
                      select=r"^deze post bevat met name vooruitontvangen",
                      rows_by_order=("accruals", "total"), sums=(Sum("total", ("accruals",)),)),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "wages", year), sign=-1)
              for year in YEARS),
            *(Link(("revenue", "total", year), ("pnl", "revenue", year)) for year in YEARS),
            MIX.check(),
        ),
        gaps={
            **MIX.gaps(),
            "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
            "impairment_player_registrations": (
                "no se publica por separado: la nota 30 (pág. 112) da una sola línea, "
                "«Afschrijvingen vergoedingssommen»; el auditor (pág. 125) dice que no hubo "
                "indicio de deterioro"),
        },
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            FigureSpec("net_result_attributable_parent", (("pnl", "attributable"),), "2025",
                       note=ATTRIBUTABLE_NOTE),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("pnl", "player_amortisation"),),
                       "2025", negate=True,
                       note="Afschrijvingen vergoedingssommen (nota 30): amortización de los "
                            "derechos de jugadores."),
            FigureSpec("profit_on_player_disposals", (("pnl", "transfer_result"),), "2025",
                       note="Resultaat vergoedingssommen (nota 31): neto de las ventas de "
                            "jugadores, jugadoras y entrenadores, menos su valor en libros."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_assets", "cash"),), "2025",
                       note="Liquide middelen (pág. 80, nota 12)."),
            *balance.split(
                "borrowings",
                (Part("bs_current_liabilities", "total"), Part("note21", "total", sign=-1),
                 Part("note22", "total", sign=-1), Part("note22", "corporate_tax"),
                 Part("note19", "current"), Part("note23", "total", sign=-1),
                 Part("note24", "total", sign=-1)),
                (Part("bs_noncurrent_liabilities", "total"), Part("note18", "closing", sign=-1),
                 Part("note19", "closing", sign=-1), Part("note20", "total", sign=-1)),
                "2025", note=BORROWINGS_NOTE, expect_zero=True),
            FigureSpec("lease_liabilities_current", (("note19", "current"),), "2025",
                       negate=True, note="Leaseverplichtingen «opgenomen onder kortlopende "
                                         "verplichtingen» (nota 19, pág. 104)."),
            FigureSpec("lease_liabilities_non_current", (("note19", "closing"),), "2025",
                       note="Eindbalans de los leaseverplichtingen a largo plazo (nota 19)."),
            FigureSpec("lease_liabilities", (("note19", "total"),), "2025",
                       note="Saldo de los leaseverplichtingen antes de separar la parte a corto "
                            "plazo (nota 19)."),
            *balance.split("transfer_payables", Part("note21", "transfers"),
                           Part("note20", "transfers"), "2025",
                           note="Crediteuren inzake vergoedingssommen (notas 20 y 21): pagos "
                                "aplazados a clubes por la compra de jugadores."),
            *balance.split("transfer_receivables", Part("note8", "transfers"),
                           Part("note6", "closing", "debtors"), "2025",
                           note="Debiteuren inzake vergoedingssommen a menos de un año (nota 8, "
                                "antes de la provisión general de 876) y deudores a más de un año "
                                "(nota 6, columna Debiteuren), que según el texto de la nota son "
                                "50,5 millones de ventas de jugadores y 0,4 millones de gastos "
                                "anticipados."),
        ),
        sentences=(
            SentenceFigureSpec(
                "shares_outstanding", 115, "uitstaande gewone aandelen",
                r"uitstaande gewone aandelen bedraagt (?P<amount>\d{1,3}(?:\.\d{3})+) voor "
                r"de boekjaren 2024/2025", "2025", unit="shares",
                note="Número medio de acciones ordinarias en circulación en 2024/25 (pág. 115), "
                     "que es el del cierre: el capital emitido no cambió (8.250 miles en los dos "
                     "años, pág. 102). Son 18.333.332 ordinarias más la acción especial "
                     "(bijzonder aandeel) de la Vereniging; el informe no menciona acciones "
                     "propias."),
        ),
    ),
)
