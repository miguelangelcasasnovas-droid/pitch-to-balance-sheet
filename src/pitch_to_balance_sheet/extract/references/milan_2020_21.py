"""AC Milan, cuentas consolidadas del grupo a 30/06/2021 (Annual Report at 30 June 2021, versión
inglesa de acmilan.com), con texto. Ejercicio de referencia de la compra de RedBird (anuncio del
01/06/2022). Principios contables italianos (OIC, pág. 31), no NIIF; formato del código civil, en
miles de euros con punto de miles.

Páginas localizadas buscando los títulos en el texto:
- pág. 25, Consolidated Financial Statements (4/5), income statement: A) Value of production, con
  1 Revenues from sales and services y 5 Other revenues and income (incluye cesiones,
  plusvalías por traspasos y otros ingresos de gestión de jugadores).
- pág. 24, (3/5), pasivo: D) Payables, con la parte a 12 meses y la de más de 12 meses.
- pág. 23, (2/5), activo: IV Cash and cash equivalents.
- pág. 56, nota de Payables: Financial payables (41.375) es «exclusively» el préstamo bancario de
  UniCredit a Casa Milan, a devolver de una vez el 18/02/2023; Payables to other financial
  institutions (83.843) son las deudas con sociedades de factoring por anticipos de cobros
  futuros, con recurso. Las dos son borrowings (plan, sección 9: el factoring entra).
- pág. 64, nota de ingresos: Other income from player management (8.133) son variables y bonus
  de traspasos (Tonali, Caldara y Pessina...): es traspaso, no ingreso.
- pág. 174: la junta de accionistas aprobó las cuentas el 26/10/2021.
La columna Change del estado no cuadra en todas las filas (p. ej. el total de payables): no se usa.
"""

from pitch_to_balance_sheet.extract import balance
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Part,
    Sum,
    TableSpec,
)

COLUMNS = ("2021", "2020", "change")
PNL_HEADER = r"^(20\d\d/20\d\d|change)$"
BALANCE_HEADER = r"^(30\.06\.20\d\d|change)$"
SALES = {
    "match": r"a\) match revenues$",
    "season_tickets": r"^b\) season tickets$",
    "other_competitions": r"^c\) revenues from other competitions$",
}
OTHER_REVENUES = {
    "sponsorship": r"^b\) sponsorship revenues$",
    "commercial": r"^d\) commercial revenues and royalties$",
    "broadcasting": r"^e\) income from the sale of broadcasting rights$",
    "miscellaneous": r"^f\) miscellaneous income$",
    "player_loans": r"^g\) revenues from player loans$",
    "player_gains": r"^h\) gains from the sale of player registration rights$",
    "player_other": r"^i\) other income from player management$",
    "other": r"^l\) other income and revenues$",
}
PLAYER_TRADING = ("player_loans", "player_gains", "player_other")
PNL_ROWS = {
    **SALES,
    "sales_total": r"^total$",
    "inventories": r"^2 changes in inventories .* finished products$",
    **OTHER_REVENUES,
    "other_revenues_total": r"^total$",
    "value_of_production": r"^total value of production \(a\)$",
}
# Las filas «Total» y «b) beyond 12 months» se repiten: cada una va detrás de la suya.
PNL_AFTER = {"sales_total": SALES["other_competitions"],
             "other_revenues_total": OTHER_REVENUES["other"]}
PAYABLES = {
    "bonds_current": r"^1 bonds a\) within 12 months$",
    "bonds_noncurrent": r"^b\) beyond 12 months$",
    "shareholders_current": r"^3 payables to shareholders for loans a\) within 12 months$",
    "shareholders_noncurrent": r"^b\) beyond 12 months$",
    "financial_current": r"^4 financial payables a\) within 12 months$",
    "financial_noncurrent": r"^b\) beyond 12 months$",
    "factoring_current": r"^5 payables to other financial institutions a\) within 12 months$",
    "factoring_noncurrent": r"^b\) beyond 12 months$",
    "advances": r"^6 advances$",
    "trade_current": r"^7 trade payables a\) within 12 months$",
    "trade_noncurrent": r"^b\) beyond 12 months$",
    "subsidiaries": r"^9 payables to subsidiaries$",
    "associates": r"^10 payables to associates$",
    "parents": r"^11 payables to parent companies$",
    "parent_control": r"^11 bis payables to companies subject to parent companies control$",
    "tax": r"^12 tax payables$",
    "pension": r"^13 payables to pension funds and social security agencies$",
    "other": r"^14 other payables$",
    "bodies_current": r"^15 payables to professional bodies a\) within 12 months$",
    "bodies_noncurrent": r"^b\) beyond 12 months$",
}
PAYABLES_AFTER = {f"{name}_noncurrent": PAYABLES[f"{name}_current"]
                  for name in ("bonds", "shareholders", "financial", "factoring", "trade",
                               "bodies")}
CASH_ROWS = {"bank": r"^1 bank and postal deposits$", "cash_in_hand": r"^3 cash in hand$",
             "total": r"^total$"}
DEBT = ("bonds", "shareholders", "financial", "factoring")

REVENUE_TOTAL_NOTE = (
    "1 Revenues from sales and services (guion en 2020/21: partidos a puerta cerrada) más 5 "
    "Other revenues and income (pág. 25). El Value of production (261.092) incluye además la "
    "variación de existencias (150), que no es ingreso."
)
REVENUE_EX_NOTE = (
    "Los ingresos menos las líneas de jugadores de 5 Other revenues and income (pág. 25): g) "
    "cesiones (63), h) plusvalías por traspasos (20.185) e i) otros ingresos de gestión de "
    "jugadores (8.133: variables y bonus de traspasos, nota de la pág. 64)."
)
BORROWINGS_NOTE = (
    "Bonds, payables to shareholders for loans (guiones), financial payables (préstamo de "
    "UniCredit a Casa Milan, 41.375) y payables to other financial institutions (factoring con "
    "recurso, 83.843), con la parte a 12 meses y la de más (págs. 24 y 56)."
)

SPEC = ClubSpec(
    club_id="milan",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«(in thousands of Euros)» en la cabecera de cada estado (págs. 23 a 25).",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"in thousands of euros",
        thousands=".",
        tables=(
            TableSpec(
                "pnl", 25, COLUMNS, PNL_ROWS,
                header=PNL_HEADER, select=r"^total value of production \(a\)$",
                after=PNL_AFTER,
                sums=(
                    Sum("sales_total", tuple(SALES), ("2021", "2020")),
                    Sum("other_revenues_total", tuple(OTHER_REVENUES), ("2021", "2020")),
                    Sum("value_of_production", ("sales_total", "inventories",
                                                "other_revenues_total"), ("2021", "2020")),
                ),
            ),
            TableSpec(
                "payables", 24, COLUMNS, PAYABLES | {"total": r"^total payables \(d\)$"},
                header=BALANCE_HEADER, select=r"^total payables \(d\)$", after=PAYABLES_AFTER,
                sums=(Sum("total", tuple(PAYABLES), ("2021",)),),
            ),
            TableSpec("cash", 23, COLUMNS, CASH_ROWS, header=BALANCE_HEADER,
                      select=CASH_ROWS["bank"], after={"total": CASH_ROWS["cash_in_hand"]},
                      sums=(Sum("total", ("bank", "cash_in_hand"), ("2021", "2020")),)),
        ),
        figures=(
            FigureSpec("revenue_total_reported",
                       (Part("pnl", "sales_total"), Part("pnl", "other_revenues_total")), "2021",
                       note=REVENUE_TOTAL_NOTE),
            FigureSpec("revenue_ex_player_trading",
                       (Part("pnl", "sales_total"), Part("pnl", "other_revenues_total"),
                        *(Part("pnl", key, sign=-1) for key in PLAYER_TRADING)), "2021",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("cash", "total"),), "2021",
                       note="IV Cash and cash equivalents, total (pág. 23)."),
            *balance.split("borrowings",
                           tuple(Part("payables", f"{name}_current") for name in DEBT),
                           tuple(Part("payables", f"{name}_noncurrent") for name in DEBT),
                           "2021", note=BORROWINGS_NOTE),
        ),
    ),
)
