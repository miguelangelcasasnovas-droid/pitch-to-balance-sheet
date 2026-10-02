"""A.S. Roma S.p.A., bilancio consolidato del gruppo a 30/06/2019 (Relazione finanziaria annuale,
asroma.com), con texto. Ejercicio de referencia de la compra de Friedkin (anuncio del
06/08/2020): el de 2019/20 se publicó en octubre de 2020. NIIF; miles de euros con punto de
miles.

Páginas localizadas buscando los títulos en el texto:
- pág. 64, Conto economico complessivo consolidato: «Totale Ricavi» sin los traspasos, que van
  en su línea, «Ricavi da gestione dei diritti pluriennali prestazioni calciatori» (148.262),
  después de los costes. La cabecera de la segunda columna dice 30.06.2019 por error: es
  2017/18.
- pág. 63, Situazione patrimoniale-finanziaria consolidata, pasivo: Finanziamenti a medio lungo
  termine (nota 10) y a breve termine (nota 18).
- pág. 62, activo: Disponibilità liquide e mezzi equivalenti.
- págs. 116 a 124, notas 10 y 18: el Facility Agreement de Goldman Sachs y UniCredit, los mutuos
  del Credito Sportivo, los descubiertos bancarios (22.388) y los préstamos de NEEP Roma Holding,
  el accionista de control (24.400 a largo y 4.680 a corto), que devengan interés solo si el
  grupo NEEP llega a cierta rentabilidad (tope del 10 %) y tienen vencimientos: van en
  borrowings, como los presenta el club. NEEP los convirtió en reserva en septiembre de 2019.
- pág. 114, nota 9: el capital son 628.882.320 acciones ordinarias. La sociedad no tiene
  acciones propias (pág. 11).
"""

from pitch_to_balance_sheet.extract import balance
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Part,
    Sum,
    TableSpec,
    TextCellSpec,
)

COLUMNS = ("2019", "2018")
PNL_HEADER = r"^30\.06\.20\d\d$"
BALANCE_HEADER = r"^20(19|18)$"
OTHER_REVENUES = {
    "sponsorship": r"^sponsorizzazioni$",
    "broadcasting": r"^diritti televisivi e diritti dimmagine$",
    "advertising": r"^pubblicita$",
    "other": r"^altri$",
}
PNL_ROWS = {
    "match": r"^ricavi da gare$",
    "commercial": r"^ricavi delle vendite commerciali e licensing$",
    **OTHER_REVENUES,
    "other_revenues": r"^altri ricavi e proventi$",
    "revenue": r"^totale ricavi$",
    "player_rights_income": r"^ricavi da gestione dei diritti pluriennali prestazioni calciatori$",
    "player_rights_costs": r"^oneri da gestione dei diritti pluriennali prestazioni calciatori$",
    "player_rights_net": r"^ricavi netti da gestione dei diritti pluriennali prestazioni "
                         r"calciatori$",
}
NONCURRENT = {
    "loans": r"^finanziamenti a medio lungo termine$",
    "employee_benefits": r"^fondo tfr benefici a dipendenti$",
    "trade": r"^debiti commerciali$",
    "tax_provision": r"^fondo rischi per imposte$",
    "tax": r"^debiti tributari$",
    "provisions": r"^fondo per rischi e oneri$",
    "other": r"^altre passivita$",
}
CURRENT = {
    "trade": r"^debiti commerciali$",
    "loans": r"^finanziamenti a breve termine$",
    "tax": r"^debiti tributari$",
    "social_security": r"^debiti verso istituti previdenziali$",
    "other": r"^altre passivita$",
}
CURRENT_ASSETS = {
    "inventories": r"^rimanenze$",
    "trade": r"^crediti commerciali$",
    "other": r"^altre attivita correnti$",
    "tax": r"^crediti per imposte$",
    "cash": r"^disponibilita liquide e mezzi equivalenti$",
}

REVENUE_EX_NOTE = (
    "Totale Ricavi (pág. 64): no incluye los traspasos ni las cesiones, que van en «Ricavi da "
    "gestione dei diritti pluriennali prestazioni calciatori» (148.262), después de los costes "
    "operativos."
)
BORROWINGS_NOTE = (
    "Finanziamenti a medio lungo termine y a breve termine (pág. 63; notas 10 y 18): el Facility "
    "Agreement, los mutuos del Credito Sportivo, descubiertos bancarios (22.388), tarjetas de "
    "crédito (153) y los préstamos de NEEP Roma Holding (24.400 y 4.680), con interés "
    "condicionado a la rentabilidad del grupo NEEP y vencimientos."
)
SHARES_NOTE = (
    "Acciones ordinarias del capital social al 30/06/2019 (nota 9, pág. 114), sin acciones "
    "propias (pág. 11)."
)

SPEC = ClubSpec(
    club_id="roma",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«Valori in € /000» en la cabecera de cada estado (págs. 62 a 64; el texto del PDF "
               "pierde el símbolo del euro).",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"/000",
        thousands=".",
        tables=(
            TableSpec(
                "pnl", 64, COLUMNS, PNL_ROWS, header=PNL_HEADER,
                sums=(
                    Sum("other_revenues", tuple(OTHER_REVENUES)),
                    Sum("revenue", ("match", "commercial", "other_revenues")),
                    Sum("player_rights_net", ("player_rights_income", "player_rights_costs")),
                ),
            ),
            TableSpec("bs_noncurrent", 63, COLUMNS, NONCURRENT | {
                          "total": r"^totale passivita non correnti$"},
                      header=BALANCE_HEADER,
                      block=(r"^passivita non correnti$", r"^totale passivita non correnti$"),
                      sums=(Sum("total", tuple(NONCURRENT)),)),
            TableSpec("bs_current", 63, COLUMNS, CURRENT | {
                          "total": r"^totale passivita correnti$"},
                      header=BALANCE_HEADER,
                      block=(r"^passivita correnti$", r"^totale passivita correnti$"),
                      sums=(Sum("total", tuple(CURRENT)),)),
            TableSpec("bs_current_assets", 62, COLUMNS, CURRENT_ASSETS | {
                          "total": r"^totale attivita correnti$"},
                      header=BALANCE_HEADER,
                      block=(r"^attivita correnti$", r"^totale attivita correnti$"),
                      sums=(Sum("total", tuple(CURRENT_ASSETS)),)),
        ),
        text_cells=(
            TextCellSpec("shares", "ordinary", 114, "Azioni ordinarie",
                         r"^(?P<amount>[\d.]+) azioni ordinarie, invariate rispetto al 30 giugno "
                         r"2018\.$", column="2019"),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "2019"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "2019",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2019",
                       note="Disponibilità liquide e mezzi equivalenti (pág. 62, nota 8)."),
            *balance.split("borrowings", Part("bs_current", "loans"),
                           Part("bs_noncurrent", "loans"), "2019", note=BORROWINGS_NOTE),
            FigureSpec("shares_outstanding", (Part("shares", "ordinary"),), "2019",
                       unit="shares", note=SHARES_NOTE),
        ),
    ),
)
