"""S.S. Lazio S.p.A., 2024/25: paquete ESEF (XHTML con iXBRL) del portal 1info.

Decisión del usuario del 27/09/2026: la fuente es el ESEF, con las cuentas consolidadas. El PDF
que publica el club es un escaneo ("copia di cortesia").

Las cifras salen de los hechos iXBRL (extract/ixbrl.py), no de páginas: cada una se cita por su
etiqueta, su contexto y el id del hecho. Solo están etiquetadas las cuentas consolidadas (págs.
138 a 145 del XHTML) y todos los contextos son de la entidad (LEI 81560036DCCA48CA0F08), sin
dimensiones. La cuenta de resultados consolidada está en la pág. 141.

Los hechos van en euros (scale 0, decimals 0). Aquí van en miles, divididos por 1.000 sin
redondear; los cuadres se hacen en euros, con los pesos del linkbase de cálculo del emisor.
Ese linkbase suma las imposte differite (4.846.836, un ingreso) con peso +1, aunque la etiqueta
es de gasto: el resultado cuadra así, y así se comprueba.
"""

from pitch_to_balance_sheet.extract.statements import (
    Calc,
    ClubSpec,
    FigureSpec,
    IxbrlDocumentSpec,
    Part,
)

LEI = "81560036DCCA48CA0F08"
PERIODS = {"2025": "2024-07-01/2025-06-30", "2024": "2023-07-01/2024-06-30"}
CONCEPTS = {
    "gate": "ext:RicaviDaGare",
    "media": "ext:DirittiRadiotelevisiEProventiMedia",
    "sponsorship": "ext:RicaviDaSponsorizzazioneEPubblicità",
    "player_rights_income": "ext:ProventiDaGestioneDirittiCalciatori",
    "other_income": "ifrs-full:OtherIncome",
    "merchandising": "ifrs-full:RevenueFromSaleOfGoods",
    "total_revenue": "ifrs-full:RevenueAndOperatingIncome",
    "materials": "ifrs-full:RawMaterialsAndConsumablesUsed",
    "staff": "ifrs-full:EmployeeBenefitsExpense",
    "services": "ifrs-full:ServicesExpense",
    "player_rights_expenses": "ext:OneriDaGestioneDirittiCalciatori",
    "other_expenses": "ifrs-full:OtherExpenseByNature",
    "amortisation": ("ifrs-full:DepreciationAmortisationAndImpairmentLossReversalOf"
                     "ImpairmentLossRecognisedInProfitOrLoss"),
    "operating_expenses": "ifrs-full:OperatingExpense",
    "disposal_gains": "ifrs-full:GainsOnDisposalsOfNoncurrentAssets",
    "disposal_losses": "ifrs-full:LossesOnDisposalsOfNoncurrentAssets",
    "disposal_result": "ifrs-full:GainsLossesOnDisposalsOfNoncurrentAssets",
    "operating_result": "ifrs-full:ProfitLossFromOperatingActivities",
    "finance_income": "ifrs-full:FinanceIncome",
    "finance_costs": "ifrs-full:FinanceCosts",
    "result_before_tax": "ifrs-full:ProfitLossBeforeTax",
    "current_tax": "ifrs-full:CurrentTaxExpenseIncome",
    "deferred_tax": "ifrs-full:DeferredTaxExpenseIncomeRecognisedInProfitOrLoss",
    "net_result": "ifrs-full:ProfitLoss",
}
CALCS = (
    Calc("total_revenue", tuple((key, 1) for key in (
        "gate", "media", "sponsorship", "player_rights_income", "other_income",
        "merchandising"))),
    Calc("operating_expenses", tuple((key, 1) for key in (
        "materials", "staff", "services", "player_rights_expenses", "other_expenses",
        "amortisation"))),
    Calc("disposal_result", (("disposal_gains", 1), ("disposal_losses", -1))),
    Calc("operating_result", (("total_revenue", 1), ("operating_expenses", -1),
                              ("disposal_result", 1))),
    Calc("result_before_tax", (("operating_result", 1), ("finance_income", 1),
                               ("finance_costs", -1))),
    Calc("net_result", (("result_before_tax", 1), ("current_tax", -1), ("deferred_tax", 1))),
)
REVENUE_NOTE = (
    "TOTALE RICAVI, que incluye «Proventi da gestione diritti calciatori» (2.899.825 euros): "
    "según la nota 32 (pág. 193), cesiones temporales de jugadores (2.553 miles) y otros "
    "proventi de jugadores (347 miles)."
)
REVENUE_EX_NOTE = (
    "TOTALE RICAVI menos Proventi da gestione diritti calciatori. Regla de la sección 9 del "
    "plan. Las plusvalías por traspasos van aparte (GainsOnDisposalsOfNoncurrentAssets)."
)
STAFF_NOTE = (
    "Costo del personale. La nota 36 (pág. 195) no desglosa indemnizaciones: sus filas de "
    "trattamento di fine carriera y di fine rapporto son provisiones de fin de contrato, como el "
    "T.F.R. de Juventus. Los 632 miles de «incentivi all'esodo» de la pág. 190 son una deuda con "
    "jugadores, no un gasto del año."
)
NET_NOTE = "UTILE (PERDITA) DI ESERCIZIO consolidado."

SPEC = ClubSpec(
    club_id="lazio",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="Unidad iso4217:EUR de los hechos iXBRL, con scale 0: euros. Se pasan a miles "
               "dividiendo por 1.000, sin redondear.",
    primary=IxbrlDocumentSpec(
        entity=LEI,
        periods=PERIODS,
        unit="iso4217:EUR",
        concepts=CONCEPTS,
        calcs=CALCS,
        figures=(
            FigureSpec("revenue_total_reported", (("ixbrl", "total_revenue"),), "2025",
                       note=REVENUE_NOTE),
            FigureSpec("revenue_ex_player_trading",
                       (Part("ixbrl", "total_revenue"),
                        Part("ixbrl", "player_rights_income", sign=-1)),
                       "2025", note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("ixbrl", "staff"),), "2025", note=STAFF_NOTE),
            FigureSpec("net_result", (("ixbrl", "net_result"),), "2025", note=NET_NOTE),
        ),
    ),
)
