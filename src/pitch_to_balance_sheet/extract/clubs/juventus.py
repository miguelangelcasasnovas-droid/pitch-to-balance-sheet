"""Juventus Football Club S.p.A., 2024/25: Relazione Finanziaria Annuale de la web del club.

Texto directo con pdfplumber, sin OCR. Fuente: la versión italiana, que prevalece. Control: la
traducción al inglés, con la misma paginación. Cada página del PDF son dos del informe:
- pág. 149, mitad izquierda: conto economico consolidato, en miles de euros ("importi in
  migliaia di Euro"), ejercicios 2024/2025 y 2023/2024. Los miles se separan con punto.
- pág. 175: nota 40 (personale tesserato), mitad izquierda, y nota 41 (altro personale), mitad
  derecha, con columnas 2024/2025, 2023/2024 y variazione. La cabecera "variazione" va en otra
  línea, así que la región de cada nota se corta antes de esa columna, que no se usa.

La cuenta de resultados no tiene una línea de total de personal: los gastos de personal son la
suma de los totales de las notas 40 y 41, que tienen que coincidir con sus líneas de la cuenta.

Fase 3a. Las partidas de ingresos son las líneas de la cuenta (mapeo en
config/line_items.yaml). Las notas de jugadores tienen también columna de variación, que se deja
fuera de la región, y debajo un detalle por jugador que la región deja fuera:
- pág. 173, mitad derecha, nota 35, proventi da gestione diritti calciatori: plusvalenze,
  cesiones temporales y otros ingresos (sell-on y bonus de traspasos).
- pág. 176, mitad izquierda, nota 42, oneri da gestione diritti calciatori: minusvalenze.
- pág. 177, mitad izquierda, nota 44, ammortamenti e svalutazioni diritti calciatori.
profit_on_player_disposals = plusvalenze − minusvalenze de las notas 35 y 42.
- pág. 174, mitad izquierda, nota 36, altri ricavi e proventi: las iniziative commerciali van a
  commercial y el resto a other (decisión del usuario del 27/09/2026).
player_trading_other_income = cesiones temporales + altri ricavi (sell-on y bonus) de la nota 35.

Fase 3b, balance al 30/06/2025:
- pág. 148: situazione patrimoniale-finanziaria consolidata, activo en la mitad izquierda y
  pasivo en la derecha. Los totales del pasivo están en negrita y el texto del PDF los duplica
  letra a letra, así que no se leen: los préstamos se cuadran con la nota 25.
- pág. 170, mitad izquierda, nota 25: prestiti e altri debiti finanziari, corrientes y no
  corrientes, con las passività IFRS 16 (arrendamientos) en su propia fila.
- pág. 169: el número de acciones, en el texto de la nota 23.
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

LEFT_HALF = (0.0, 0.0, 0.5, 1.0)
RIGHT_HALF = (0.5, 0.0, 1.0, 1.0)
NOTE25_COLUMNS = ("current_2025", "non_current_2025", "current_2024", "non_current_2024")
BORROWINGS_NOTE = (
    "Prestiti e altri debiti finanziari (nota 25) sin las passività IFRS 16: anticipos de "
    "sociedades de factoring (244.776 en total), la hipoteca de la sede y el Training Center "
    "Continassa, préstamos bancarios y el préstamo del Istituto per il Credito Sportivo. El "
    "propio club presenta los anticipos de factoring como deuda financiera."
)
# Notas de la pág. 175 sin la columna de variación: sus cifras acaban en el 43,6% y el 93,7%
# del ancho, y las de 2023/2024, en el 38,1% y el 88,2%.
NOTE40_REGION = (0.0, 0.0, 0.39, 1.0)
NOTE41_REGION = (0.5, 0.0, 0.89, 1.0)
YEARS = ("2025", "2024")
REVENUE = ("gate", "media", "sponsorship", "products", "player_rights_income", "other_income")
COSTS = ("materials", "goods_for_sale", "external_services", "registered_personnel",
         "other_personnel", "player_rights_expenses", "other_expenses")
PNL_SUMS = (
    Sum("total_revenue", REVENUE),
    Sum("total_operating_costs", COSTS),
    Sum("operating_result", ("total_revenue", "total_operating_costs", "player_amortisation",
                             "other_amortisation", "provisions")),
    Sum("result_before_tax", ("operating_result", "financial_income", "financial_expenses",
                              "associates")),
    Sum("net_result", ("result_before_tax", "current_taxes", "deferred_taxes")),
)
REVENUE_NOTE = (
    "Total publicado, que incluye «Proventi da gestione diritti calciatori» (109.725): ingresos "
    "por traspasos y cesiones de jugadores."
)
REVENUE_EX_NOTE = (
    "Totale ricavi e proventi menos Proventi da gestione diritti calciatori. Regla de la "
    "sección 9 del plan."
)
SEVERANCE_NOTE = (
    "Incentivazioni all'esodo (nota 40, pág. 175): una fila ordinaria dentro del personal "
    "tesserato, sin clasificar como excepcional. Informativa: no ajusta ninguna métrica."
)
MIX = mix.for_club("juventus")
DISPOSALS_NOTE = (
    "Plusvalenze (nota 35) menos minusvalenze (nota 42) de cesión de derechos de jugadores y "
    "jugadoras. Fuera quedan las cesiones temporales y los «altri ricavi» (sell-on y bonus) de "
    "la nota 35, que no tienen concepto (ver config/line_items.yaml)."
)
STAFF_NOTE = (
    "Suma de los totales de las notas 40 (personale tesserato) y 41 (altro personale): la "
    "cuenta de resultados no tiene una línea de total de personal."
)


def document(language: str, control_index: int | None) -> DocumentSpec:
    italian = language == "it"
    pnl_rows = {
        "gate": r"^ricavi da gare$" if italian else r"^ticket sales$",
        "media": (r"^diritti audiovisivi e proventi media$" if italian
                  else r"^broadcasting revenues$"),
        "sponsorship": (r"^ricavi da sponsorizzazioni e pubblicita$" if italian
                        else r"^revenues from sponsorship and advertising$"),
        "products": (r"^ricavi da vendite di prodotti e licenze$" if italian
                     else r"^revenues from sales of products and licences$"),
        "player_rights_income": (r"^proventi da gestione diritti calciatori$" if italian
                                 else r"^revenues from players registration rights$"),
        "other_income": r"^altri ricavi e proventi$" if italian else r"^other income$",
        "total_revenue": r"^totale ricavi e proventi$" if italian else r"^total revenues$",
        "materials": (r"^acquisti di materiali" if italian
                      else r"^cost of raw materials and other consumables$"),
        "goods_for_sale": (r"^acquisti di prodotti per la vendita$" if italian
                           else r"^cost of goods for sale$"),
        "external_services": r"^servizi esterni$" if italian else r"^external services$",
        "registered_personnel": (r"^personale tesserato$" if italian
                                 else r"^registered players and technical staff$"),
        "other_personnel": (r"^altro personale$" if italian
                            else r"^other personnel expenses$"),
        "player_rights_expenses": (r"^oneri da gestione diritti calciatori$" if italian
                                   else r"^expenses from players registration rights$"),
        "other_expenses": r"^altri oneri$" if italian else r"^other operating expenses$",
        "total_operating_costs": (r"^totale costi operativi$" if italian
                                  else r"^total operating expenses$"),
        "player_amortisation": (r"^ammortamenti e svalutazioni diritti calciatori$" if italian
                                else r"^amortisation and write-downs of players registration "
                                     r"rights$"),
        "other_amortisation": (r"^ammortamenti altre attivita" if italian
                               else r"^depreciation/amortisation of other tangible"),
        "provisions": r"^accantonamenti e altre svalutazioni" if italian else r"^provisions,",
        "operating_result": (r"^risultato operativo$" if italian
                             else r"^operating profit \(loss\)$"),
        "financial_income": r"^proventi finanziari$" if italian else r"^financial income$",
        "financial_expenses": r"^oneri finanziari$" if italian else r"^financial expenses$",
        "associates": (r"^quota di pertinenza del risultato" if italian
                       else r"^equity-accounted profit \(loss\)"),
        "result_before_tax": (r"^risultato prima delle imposte$" if italian
                              else r"^profit \(loss\) before tax$"),
        "current_taxes": r"^imposte correnti$" if italian else r"^current taxes$",
        "deferred_taxes": (r"^imposte differite e anticipate$" if italian
                           else r"^deferred taxes$"),
        "net_result": (r"^risultato dellesercizio$" if italian
                       else r"^profit \(loss\) for the year$"),
    }
    note40_rows = {
        "wages": r"^retribuzioni$" if italian else r"^wages and salaries$",
        "variable_bonuses": r"^premi variabili$" if italian else r"^variable bonuses$",
        "contributions": r"^contributi$" if italian else r"^social security contributions$",
        "termination_incentives": (r"^incentivazioni allesodo$" if italian
                                   else r"^termination incentives$"),
        "loaned_players": (r"^compensi a calciatori temporaneamente trasferiti$" if italian
                           else r"^compensation to temporarily transferred players$"),
        "severance": r"^t\.f\.r\.$" if italian else r"^italian post-employment benefits$",
        "scholarships": r"^borse di studio$" if italian else r"^scholarships$",
        "extraordinary": (r"^altri compensi straordinari tesserati$" if italian
                          else r"^other extraordinary compensation$"),
        "other": r"^altri oneri$" if italian else r"^other operating expenses$",
        "total": (r"^personale tesserato$" if italian
                  else r"^registered players and technical staff$"),
    }
    note41_rows = {
        "wages": r"^retribuzioni$" if italian else r"^wages and salaries$",
        "contributions": r"^contributi$" if italian else r"^social security contributions$",
        "variable_bonuses": r"^premi variabili$" if italian else r"^variable bonuses$",
        "severance": r"^t\.f\.r\.$" if italian else r"^italian post-employment benefits$",
        "other": r"^altri oneri$" if italian else r"^other operating expenses$",
        "total": r"^altro personale$" if italian else r"^other personnel expenses$",
    }
    header_years = r"^\d{4}/\d{4}$"
    note35_rows = {
        "gains_male": (r"^plusvalenze da cessione diritti calciatori$" if italian
                       else r"^gains on disposal of male players registration rights$"),
        "gains_female": (r"^plusvalenze da cessione diritti calciatrici$" if italian
                         else r"^gains on disposal of female players registration rights$"),
        "other": r"^altri ricavi$" if italian else r"^other revenues$",
        "total": (r"^proventi da gestione diritti calciatori$" if italian
                  else r"^revenues from players registration rights$"),
    }
    note42_rows = {
        "temporary": (r"^oneri per acquisto temporaneo diritti calciatori$" if italian
                      else r"^expenses for the temporary acquisition of players registration "
                           r"rights$"),
        "losses_male": (r"^minusvalenze da cessione diritti calciatori$" if italian
                        else r"^losses on disposal of male players registration rights$"),
        "losses_youth": (r"^minusvalenze da cessione diritti calciatori giovani di serie$"
                         if italian else r"^losses on disposal of registered youth players "
                                         r"registration rights$"),
        "losses_female": (r"^minusvalenze da cessione diritti calciatrici$" if italian
                          else r"^losses on disposal of female players registration rights$"),
        "other": r"^altri oneri$" if italian else r"^other operating expenses$",
        "total": (r"^oneri da gestione diritti calciatori$" if italian
                  else r"^expenses from players registration rights$"),
    }
    if italian:  # rótulo en dos líneas con las cifras en medio: la fila sin rótulo de después
        note42_rows["ancillary_label"] = (r"^oneri accessori su diritti pluriennali calciatori e "
                                          r"tesserati non$")
        note42_after = {"ancillary": "ancillary_label"}
    else:  # en inglés las cifras van con la primera línea del rótulo
        note42_rows["ancillary"] = (r"^ancillary costs for non-capitalised players and technical "
                                    r"staffs$")
        note42_after = {}
    # En inglés el rótulo se parte en dos líneas; las cifras van en la primera.
    note35_rows["temporary"] = (r"^ricavi per cessione temporanea diritti calciatori/calciatrici$"
                                if italian else r"^revenues from the temporary disposal of "
                                                r"players registra-$")
    note36_rows = {
        "commercial_initiatives": (r"^proventi da iniziative commerciali$" if italian
                                   else r"^income from commercial initiatives$"),
        "estimates": (r"^proventi da aggiornamenti di stime$" if italian
                      else r"^income from estimate adjustments$"),
        "lca": r"^contributi da lca e vari$" if italian else r"^contributions from lca and others$",
        "hotel": r"^servizi alberghieri$" if italian else r"^hotel services$",
        "insurance": (r"^indennizzi e altri proventi assicurativi$" if italian
                      else r"^insurance compensation and other insurance-related income$"),
        "stadium_events": (r"^proventi da eventi e attivita stadio no match day$" if italian
                           else r"^income from no match day events and stadium activities$"),
        "rents": r"^affitti attivi$" if italian else r"^rental income$",
        "other": r"^altri$" if italian else r"^other$",
        "total": r"^altri ricavi e proventi$" if italian else r"^other income$",
    }
    note44_rows = {
        "amortisation": r"^ammortamenti$" if italian else r"^amortisation$",
        "male": r"^calciatori professionisti$" if italian else r"^male professional players$",
        "youth": r"^giovani di serie$" if italian else r"^registered youth players$",
        "female": r"^calciatrici$" if italian else r"^female players$",
        "write_downs": r"^svalutazioni$" if italian else r"^write-downs$",
        "total": (r"^ammortamenti e svalutazioni diritti calciatori$" if italian
                  else r"^amortisation and write-downs of players registration rights$"),
    }
    balance_header = r"^30/06/20\d\d$" if italian else r"^20\d\d$"
    noncurrent_assets = {
        "players": (r"^diritti pluriennali alle prestazioni dei calciatori, netti$" if italian
                    else r"^players registration rights, net$"),
        "goodwill": r"^avviamento$" if italian else r"^goodwill$",
        "other_intangibles": (r"^altre attivita immateriali$" if italian
                              else r"^other intangible assets$"),
        "intangibles_in_progress": (r"^immobilizzazioni immateriali in corso" if italian
                                    else r"^intangible assets in progress"),
        "land": r"^terreni e fabbricati$" if italian else r"^land and buildings$",
        "other_tangibles": (r"^altre attivita materiali$" if italian
                            else r"^other tangible assets$"),
        "tangibles_in_progress": (r"^immobilizzazioni materiali in corso" if italian
                                  else r"^tangible assets in progress"),
        "investments": r"^partecipazioni$" if italian else r"^equity investments$",
        "financial": (r"^attivita finanziarie non correnti$" if italian
                      else r"^non-current financial assets$"),
        "deferred_tax": r"^imposte differite attive$" if italian else r"^deferred tax assets$",
        "transfers": (r"^crediti verso societa calcistiche per campagne trasferimenti$" if italian
                      else r"^receivables from football clubs for transfer campaigns$"),
        "other": r"^altre attivita non correnti$" if italian else r"^other non-current assets$",
        "advances": (r"^anticipi versati non correnti$" if italian
                     else r"^non-current advances paid$"),
        "total": (r"^totale attivita non correnti$" if italian
                  else r"^total non-current assets$"),
    }
    current_assets = {
        "inventories": r"^rimanenze$" if italian else r"^inventories$",
        "trade": r"^crediti commerciali$" if italian else r"^trade receivables$",
        "related": (r"^crediti commerciali e altri crediti verso parti correlate$" if italian
                    else r"^trade and other receivables from related parties$"),
        "transfers": noncurrent_assets["transfers"],
        "other": r"^altre attivita correnti$" if italian else r"^other current assets$",
        "financial": (r"^attivita finanziarie correnti$" if italian
                      else r"^current financial assets$"),
        "cash": r"^disponibilita liquide$" if italian else r"^cash and cash equivalents$",
        "advances": (r"^anticipi versati correnti$" if italian
                     else r"^current advances paid$"),
        "total": r"^totale attivita correnti$" if italian else r"^total current assets$",
    }
    liabilities = {
        "loans": (r"^prestiti e altri debiti finanziari$" if italian
                  else r"^bank loans and other financial liabilities$"),
        "transfers": (r"^debiti verso societa calcistiche per campagne trasferimenti$" if italian
                      else r"^payables to football clubs related to transfer campaigns$"),
    }
    note25_rows = {
        "leases": r"^passivita ifrs 16\b" if italian else r"^lease liabilities\b",
        "total": (r"^prestiti ed altri debiti finanziari\b" if italian
                  else r"^bank liabilities loans and other financial\b"),
    }
    return DocumentSpec(
        method="text",
        unit_evidence=r"migliaia di euro" if italian else r"thousands of euro",
        thousands="." if italian else ",",
        control_index=control_index,
        tables=(
            TableSpec("pnl", 149, YEARS, pnl_rows, sums=PNL_SUMS, region=LEFT_HALF,
                      header=header_years),
            TableSpec("note40", 175, YEARS, note40_rows, region=NOTE40_REGION,
                      header=header_years, select=note40_rows["scholarships"],
                      sums=(Sum("total", tuple(note40_rows)[:-1]),)),
            TableSpec("note41", 175, YEARS, note41_rows, region=NOTE41_REGION,
                      header=header_years, select=note41_rows["total"],
                      sums=(Sum("total", tuple(note41_rows)[:-1]),)),
            TableSpec("note35", 173, YEARS, note35_rows, region=(0.5, 0.0, 0.89, 0.28),
                      header=header_years,
                      sums=(Sum("total", ("gains_male", "temporary", "gains_female", "other")),)),
            TableSpec("note42", 176, YEARS, note42_rows, region=(0.0, 0.0, 0.39, 0.34),
                      header=header_years, totals_after=note42_after,
                      sums=(Sum("total", ("ancillary", "temporary", "losses_male", "losses_youth",
                                          "losses_female", "other")),)),
            TableSpec("note36", 174, YEARS, note36_rows, region=(0.0, 0.0, 0.39, 0.43),
                      header=header_years, select=note36_rows["commercial_initiatives"],
                      sums=(Sum("total", tuple(note36_rows)[:-1]),)),
            TableSpec("note44", 177, YEARS, note44_rows,
                      region=(0.0, 0.0, 0.39, 0.76 if italian else 0.78), header=header_years,
                      select=note44_rows["write_downs"],
                      sums=(Sum("amortisation", ("male", "youth", "female")),
                            Sum("total", ("amortisation", "write_downs")))),
            # Fase 3b: balance y nota 25.
            TableSpec("bs_noncurrent_assets", 148, YEARS, noncurrent_assets, region=LEFT_HALF,
                      header=balance_header,
                      block=(r"^attivita non correnti$" if italian else r"^non-current assets$",
                             noncurrent_assets["total"]),
                      sums=(Sum("total", tuple(noncurrent_assets)[:-1]),)),
            TableSpec("bs_current_assets", 148, YEARS, current_assets, region=LEFT_HALF,
                      header=balance_header,
                      block=(r"^attivita correnti$" if italian else r"^current assets$",
                             current_assets["total"]),
                      sums=(Sum("total", tuple(current_assets)[:-1]),)),
            TableSpec("bs_noncurrent_liabilities", 148, YEARS, liabilities, region=RIGHT_HALF,
                      header=balance_header,
                      block=(r"^passivita non correnti$" if italian
                             else r"^non-current liabilities$",
                             r"^totale passivita non correnti" if italian
                             else r"^total non-current liabilities")),
            TableSpec("bs_current_liabilities", 148, YEARS, liabilities, region=RIGHT_HALF,
                      header=balance_header,
                      block=(r"^passivita correnti$" if italian else r"^current liabilities$",
                             r"^totale passivita correnti" if italian
                             else r"^total current liabilities")),
            TableSpec("note25", 170, NOTE25_COLUMNS, note25_rows, region=LEFT_HALF,
                      header=r"^corrente$" if italian else r"^(current|non-current)$",
                      select=note25_rows["leases"],
                      # Debajo, en la misma columna, va el calendario de vencimientos, con las
                      # mismas filas en otro orden.
                      block=(r"^anticipi finanziari da societa di factoring" if italian
                             else r"^advances from factoring companies", note25_rows["total"])),
        ),
        links=(
            *(Link((note, "total", year), ("pnl", line, year), sign=-1)
              for note, line in (("note40", "registered_personnel"), ("note41", "other_personnel"),
                                 ("note42", "player_rights_expenses"),
                                 ("note44", "player_amortisation"))
              for year in YEARS),
            *(Link(("note35", "total", year), ("pnl", "player_rights_income", year))
              for year in YEARS),
            *(Link(("note36", "total", year), ("pnl", "other_income", year)) for year in YEARS),
            MIX.check(),
            # La nota 25 es la línea de préstamos del balance, corriente y no corriente.
            *(Link(("note25", "total", f"{part}_{year}"), (table, "loans", year))
              for part, table in (("current", "bs_current_liabilities"),
                                  ("non_current", "bs_noncurrent_liabilities"))
              for year in YEARS),
        ),
        gaps=MIX.gaps(),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "total_revenue"),), "2025",
                       note=REVENUE_NOTE),
            FigureSpec("revenue_ex_player_trading",
                       (Part("pnl", "total_revenue"),
                        Part("pnl", "player_rights_income", sign=-1)),
                       "2025", note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("note40", "total"), ("note41", "total")), "2025",
                       note=STAFF_NOTE),
            FigureSpec("staff_severance_disclosed", (("note40", "termination_incentives"),),
                       "2025", note=SEVERANCE_NOTE, included_in_staff_costs="true"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("note44", "amortisation"),),
                       "2025", note="Ammortamenti de la nota 44 (profesionales, jóvenes y "
                                    "jugadoras)."),
            FigureSpec("impairment_player_registrations", (("note44", "write_downs"),), "2025",
                       note="Svalutazioni de la nota 44."),
            FigureSpec("profit_on_player_disposals",
                       (Part("note35", "gains_male"), Part("note35", "gains_female"),
                        Part("note42", "losses_male", sign=-1),
                        Part("note42", "losses_youth", sign=-1),
                        Part("note42", "losses_female", sign=-1)),
                       "2025", note=DISPOSALS_NOTE),
            FigureSpec("player_trading_other_income",
                       (("note35", "temporary"), ("note35", "other")), "2025",
                       note="Cesiones temporales (3.754) y altri ricavi: sell-on fees y bonus de "
                            "traspasos (16.101), de la nota 35. Fuera de "
                            "profit_on_player_disposals y de los ingresos."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Disponibilità liquide (pág. 148, nota 22)."),
            *balance.split(
                "borrowings",
                (Part("note25", "total", "current_2025"),
                 Part("note25", "leases", "current_2025", sign=-1)),
                (Part("note25", "total", "non_current_2025"),
                 Part("note25", "leases", "non_current_2025", sign=-1)),
                "2025", note=BORROWINGS_NOTE),
            *balance.split("lease_liabilities", Part("note25", "leases", "current_2025"),
                           Part("note25", "leases", "non_current_2025"), "2025",
                           note="Passività IFRS 16 de la nota 25."),
            *balance.split("transfer_payables", Part("bs_current_liabilities", "transfers"),
                           Part("bs_noncurrent_liabilities", "transfers"), "2025",
                           note="Debiti verso società calcistiche per campagne trasferimenti "
                                "(pág. 148, nota 26)."),
            *balance.split("transfer_receivables", Part("bs_current_assets", "transfers"),
                           Part("bs_noncurrent_assets", "transfers"), "2025",
                           note="Crediti verso società calcistiche per campagne trasferimenti "
                                "(pág. 148, nota 17)."),
        ),
        sentences=(
            SentenceFigureSpec(
                "shares_outstanding", 169,
                "azioni ordinarie" if italian else "ordinary shares",
                (r"rappresentato da n\. (?P<amount>\d{1,3}(?:\.\d{3})+)" if italian
                 else r"is made up of (?P<amount>\d{1,3}(?:,\d{3})+) ordinary"),
                "2025", unit="shares",
                note="Acciones ordinarias de la matriz al 30/06/2025 (nota 23): una sola clase, "
                     "sin cambios en el año según la propia nota, que no menciona acciones "
                     "propias. La nota 34 (pág. 179) da un número medio de acciones de "
                     "280.715.880 en los dos ejercicios, que no casa con esto (ver "
                     "docs/incoherencias-fuentes.md)."),
        ),
    )


SPEC = ClubSpec(
    club_id="juventus",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«importi in migliaia di Euro» en las págs. 149 y 175 de la versión italiana "
               "(«amounts in thousands of Euro» en la inglesa).",
    primary=document("it", None),
    controls=(document("en", 0),),
)
