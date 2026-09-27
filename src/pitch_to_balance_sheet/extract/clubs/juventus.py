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
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    Part,
    Sum,
    TableSpec,
)

LEFT_HALF = (0.0, 0.0, 0.5, 1.0)
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
        ),
        links=tuple(
            Link((note, "total", year), ("pnl", line, year), sign=-1)
            for note, line in (("note40", "registered_personnel"), ("note41", "other_personnel"))
            for year in YEARS
        ),
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
