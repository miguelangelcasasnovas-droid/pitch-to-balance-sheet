"""S.S. Lazio S.p.A., 2024/25: paquete ESEF (XHTML con iXBRL) del portal 1info.

Decisión del usuario del 27/09/2026: la fuente es el ESEF, con las cuentas consolidadas. El PDF
que publica el club es un escaneo ("copia di cortesia").

Las cifras salen de los hechos iXBRL (extract/ixbrl.py), no de páginas: cada una se cita por su
etiqueta, su contexto y el id del hecho. Solo están etiquetadas las cuentas consolidadas (págs.
138 a 145 del XHTML) y todos los contextos son de la entidad (LEI 81560036DCCA48CA0F08), sin
dimensiones. La cuenta de resultados consolidada está en la pág. 141.

Los hechos van en euros (scale 0, decimals 0) y así se guardan, exactos (decisión del
usuario del 27/09/2026 y sección 5 del plan); las tablas los muestran en miles redondeados. Los
cuadres se hacen en euros, con los pesos del linkbase de cálculo del emisor.
Ese linkbase suma las imposte differite (4.846.836, un ingreso) con peso +1, aunque la etiqueta
es de gasto: el resultado cuadra así, y así se comprueba.

Fase 3a. Las partidas de ingresos son las etiquetas de la cuenta (mapeo en
config/line_items.yaml); el cálculo de TOTALE RICAVI comprueba que no falta ninguna. Las notas
de jugadores no están etiquetadas: se leen de las tablas del XHTML, en miles de euros, citadas
por página y fila:
- pág. 174: movimiento de los diritti pluriennali prestazioni tesserati, bloque del fondo de
  amortización, columna Totale ("Quota dell'esercizio").
- pág. 199, nota 40: "Svalutazione delle immobilizzazioni", que según la pág. 200 son todas de
  derechos de jugadores.
El beneficio por traspasos sí está etiquetado: plusvalenze menos minusvalenze, en euros.

Fase 3b, balance al 30/06/2025:
- Etiquetados (págs. 138-139, en euros): la caja, y los créditos y deudas «verso enti settore
  specifico», corrientes y no corrientes, que son los saldos por traspasos con clubes y con la
  Lega (el estado de flujos los llama «lega c/trasferimenti»). Los totales del activo y del
  pasivo, corriente y no corriente, cuadran con sus líneas con el linkbase del emisor.
- La deuda financiera y los arrendamientos salen de la posizione finanziaria netta consolidada
  (pág. 167, tabla sin etiquetar), en millones de euros con dos decimales: el balance da los
  «Debiti finanziari» con los arrendamientos dentro, y la nota 16 solo da en miles la parte no
  corriente de los arrendamientos (1.279). Las cifras quedan en decenas de miles de euros (la
  unidad del último decimal publicado).
- pág. 181: el número de acciones, en el texto de la nota 15. Lazio no tiene acciones propias
  (pág. 116).
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    Calc,
    ClubSpec,
    FigureSpec,
    IxbrlDocumentSpec,
    Part,
    SentenceFigureSpec,
    Sum,
    XhtmlTableSpec,
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
INSTANTS = {"2025": "2025-06-30", "2024": "2024-06-30"}
BALANCE_CONCEPTS = {
    # Activo no corriente
    "ppe": "ifrs-full:PropertyPlantAndEquipment",
    "investment_property": "ifrs-full:InvestmentProperty",
    "right_of_use": "ifrs-full:RightofuseAssets",
    "player_rights": "ext:DirittiPluriennaliPrestazioniTesserati",
    "other_intangibles": "ifrs-full:IntangibleAssetsOtherThanGoodwill",
    "other_noncurrent_assets": "ifrs-full:OtherNoncurrentAssets",
    "receivables_football_noncurrent": "ext:CreditiVersoEntiSettoreSpecificoNonCorrenti",
    "deferred_tax_assets": "ifrs-full:DeferredTaxAssets",
    "tax_assets_noncurrent": "ifrs-full:CurrentTaxAssetsNoncurrent",
    "noncurrent_assets": "ifrs-full:NoncurrentAssets",
    # Activo corriente
    "inventories": "ifrs-full:Inventories",
    "trade_receivables": "ifrs-full:CurrentTradeReceivables",
    "receivables_football_current": "ext:CreditiVersoEntiSettoreSpecificoCorrenti",
    "other_current_assets": "ifrs-full:OtherCurrentAssets",
    "tax_assets_current": "ifrs-full:CurrentTaxAssetsCurrent",
    "cash": "ifrs-full:CashAndCashEquivalents",
    "current_assets": "ifrs-full:CurrentAssets",
    # Pasivo no corriente
    "financial_debt_noncurrent": "ifrs-full:OtherNoncurrentFinancialLiabilities",
    "tax_liabilities_noncurrent": "ifrs-full:CurrentTaxLiabilitiesNoncurrent",
    "payables_football_noncurrent": "ext:DebitiVersoEntiSettoreSpecificoNonCorrenti",
    "deferred_tax_liabilities": "ifrs-full:DeferredTaxLiabilities",
    "provisions_noncurrent": "ifrs-full:OtherLongtermProvisions",
    "employee_benefits": "ifrs-full:ProvisionsForEmployeeBenefits",
    "other_noncurrent_liabilities": "ifrs-full:OtherNoncurrentLiabilities",
    "noncurrent_liabilities": "ifrs-full:NoncurrentLiabilities",
    # Pasivo corriente
    "financial_debt_current": "ifrs-full:OtherCurrentFinancialLiabilities",
    "tax_liabilities_current": "ifrs-full:CurrentTaxLiabilitiesCurrent",
    "payables_football_current": "ext:DebitiVersoEntiSettoreSpecificoCorrenti",
    "trade_payables": "ifrs-full:TradeAndOtherPayablesToTradeSuppliers",
    "other_current_liabilities": "ifrs-full:OtherCurrentNonfinancialLiabilities",
    "uncertain_tax": "ext:PassivitàPerFiscalitàIncerta",
    "current_liabilities": "ifrs-full:CurrentLiabilities",
}
BALANCE_CALCS = (
    Calc("noncurrent_assets", tuple((key, 1) for key in (
        "ppe", "investment_property", "right_of_use", "player_rights", "other_intangibles",
        "other_noncurrent_assets", "receivables_football_noncurrent", "deferred_tax_assets",
        "tax_assets_noncurrent"))),
    Calc("current_assets", tuple((key, 1) for key in (
        "inventories", "trade_receivables", "receivables_football_current",
        "other_current_assets", "tax_assets_current", "cash"))),
    Calc("noncurrent_liabilities", tuple((key, 1) for key in (
        "financial_debt_noncurrent", "tax_liabilities_noncurrent",
        "payables_football_noncurrent", "deferred_tax_liabilities", "provisions_noncurrent",
        "employee_benefits", "other_noncurrent_liabilities"))),
    Calc("current_liabilities", tuple((key, 1) for key in (
        "financial_debt_current", "tax_liabilities_current", "payables_football_current",
        "trade_payables", "other_current_liabilities", "uncertain_tax"))),
)
PFN_ROWS = {
    "e_other": r"^\.verso altri finanziatori e diversi$",
    "e_related": r"^\.verso soggetti correlati$",
    "f_other": r"^\.verso altri finanziatori e diversi$",
    "f_leases": r"^\.verso contratti di locazione$",
    "g_total": r"^g\. indebitamento finanziario corrente",
}
PFN_NONCURRENT_ROWS = {
    "i_other": r"^\.verso altri finanziatori e diversi$",
    "i_leases": r"^\.verso contratti di locazione$",
    "j_bonds": r"^j\. strumenti di debito$",
    "k_trade": r"^k\. debiti commerciali e altri debiti non correnti$",
    "l_total": r"^l\. indebitamento finanziario non corrente",
}
PFN_NOTE = (
    "Posizione finanziaria netta consolidada (pág. 167), en millones con dos decimales y en "
    "negativo: la cifra queda en decenas de miles de euros y en positivo. "
)
FOOTBALL_NOTE = (
    "Crediti / debiti verso enti settore specifico (págs. 138-139, etiquetados): saldos por "
    "traspasos con clubes y con la Lega, que liquida los traspasos entre clubes italianos (el "
    "estado de flujos los llama «lega c/trasferimenti»). Los créditos corrientes incluyen además "
    "6.523 miles con la Lega y la FIGC y 170 con la UEFA, netos de una provisión de 4.354 que la "
    "nota 7 (pág. 179) no reparte."
)

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
MIX = mix.for_club("lazio")
FUND_ROWS = {
    "opening": r"^al 1 luglio 2024$",
    "disposals": r"^decrementi$",
    "charge": r"^quota dellesercizio$",
    "closing": r"^al 30 giugno 2025$",
}
WRITEDOWN_ROWS = {
    "intangible": r"^ammortamenti immobilizzazioni immateriali$",
    "tangible": r"^ammortamenti immobilizzazioni materiali$",
    "right_of_use": r"^amm.to dei diritti duso$",
    "impairment": r"^svalutazione delle immobilizzazioni$",
    "total": r"^totale$",
}

SPEC = ClubSpec(
    club_id="lazio",
    currency="EUR",
    unit="units",
    multiplier=1,
    unit_basis="Unidad iso4217:EUR de los hechos iXBRL, con scale 0 y decimals 0: euros, "
               "guardados tal cual.",
    primary=IxbrlDocumentSpec(
        entity=LEI,
        periods=PERIODS,
        unit="iso4217:EUR",
        concepts=CONCEPTS,
        calcs=CALCS + BALANCE_CALCS,
        figures=(
            FigureSpec("revenue_total_reported", (("ixbrl", "total_revenue"),), "2025",
                       note=REVENUE_NOTE),
            FigureSpec("revenue_ex_player_trading",
                       (Part("ixbrl", "total_revenue"),
                        Part("ixbrl", "player_rights_income", sign=-1)),
                       "2025", note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("ixbrl", "staff"),), "2025", note=STAFF_NOTE),
            FigureSpec("net_result", (("ixbrl", "net_result"),), "2025", note=NET_NOTE),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (Part("fund", "charge", "total"),),
                       "2025", negate=True, unit="thousands",
                       note="Quota dell'esercizio del fondo de amortización de los diritti "
                            "pluriennali prestazioni tesserati (pág. 174), en miles; la pág. 200 "
                            "da la misma cifra, 32.709, para jugadores y entrenadores."),
            FigureSpec("impairment_player_registrations", (("writedowns", "impairment"),), "2025",
                       unit="thousands",
                       note="Svalutazione delle immobilizzazioni (nota 40, pág. 199), en miles: "
                            "según la pág. 200, todas de derechos de jugadores."),
            FigureSpec("profit_on_player_disposals", (("ixbrl", "disposal_result"),), "2025",
                       note="RICAVI NETTI DA CESSIONE DIRITTI PLURIENNALI PRESTAZIONI TESSERATI: "
                            "plusvalenze (11.491.495) menos minusvalenze (347.822)."),
            FigureSpec("player_trading_other_income", (("ixbrl", "player_rights_income"),),
                       "2025",
                       note="Proventi da gestione diritti calciatori: según la nota 32 (pág. 193), "
                            "cesiones temporales (2.553 miles) y otros proventi de jugadores (347 "
                            "miles). Fuera de los ingresos sin traspasos."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("ixbrl", "cash"),), "2025",
                       note="Disponibilità liquide e mezzi equivalenti (pág. 138)."),
            *balance.split(
                "borrowings",
                (Part("pfn_current", "e_other"), Part("pfn_current", "e_related"),
                 Part("pfn_current", "f_other")),
                (Part("pfn_noncurrent", "i_other"), Part("pfn_noncurrent", "j_bonds")),
                "2025", unit="ten_thousands", negate=True,
                note=PFN_NOTE + "Debiti finanziari sin los contratti di locazione: sobre todo "
                     "anticipos de factoring sobre créditos por traspasos y derechos de "
                     "televisión, anticipos de venta de entradas y los préstamos del Medio "
                     "Credito Centrale y del Istituto per il Credito Sportivo (notas 16 y 23)."),
            *balance.split("lease_liabilities", Part("pfn_current", "f_leases"),
                           Part("pfn_noncurrent", "i_leases"), "2025", unit="ten_thousands",
                           negate=True,
                           note=PFN_NOTE + "Debiti verso contratti di locazione (NIIF 16)."),
            *balance.split("transfer_payables", Part("ixbrl", "payables_football_current"),
                           Part("ixbrl", "payables_football_noncurrent"), "2025",
                           note=FOOTBALL_NOTE),
            *balance.split("transfer_receivables", Part("ixbrl", "receivables_football_current"),
                           Part("ixbrl", "receivables_football_noncurrent"), "2025",
                           note=FOOTBALL_NOTE),
        ),
        tables=(
            XhtmlTableSpec("fund", 174, ("total",), (6,), FUND_ROWS, select=FUND_ROWS["charge"],
                           block=(r"^fondo ammortamenti$", FUND_ROWS["closing"]),
                           sums=(Sum("closing", ("opening", "disposals", "charge")),)),
            XhtmlTableSpec("writedowns", 199, ("2025", "2024"), (1, 2), WRITEDOWN_ROWS,
                           select=WRITEDOWN_ROWS["impairment"],
                           sums=(Sum("total", ("intangible", "tangible", "right_of_use",
                                               "impairment")),)),
            # Fase 3b: posizione finanziaria netta consolidada, en millones con dos decimales.
            XhtmlTableSpec("pfn_current", 167, ("2025", "2024"), (1, 3), PFN_ROWS,
                           select=r"^d\. liquidita \(a b c\)$", decimals=2,
                           after={"e_other": r"^e\. debiti finanziari correnti$",
                                  "f_other": r"^f\. parte corrente"},
                           block=(r"^e\. debiti finanziari correnti$", PFN_ROWS["g_total"]),
                           sums=(Sum("g_total", ("e_other", "e_related", "f_other",
                                                 "f_leases")),)),
            XhtmlTableSpec("pfn_noncurrent", 167, ("2025", "2024"), (1, 3), PFN_NONCURRENT_ROWS,
                           select=r"^d\. liquidita \(a b c\)$", decimals=2,
                           block=(r"^i\. debiti finanziari non correnti$",
                                  PFN_NONCURRENT_ROWS["l_total"]),
                           sums=(Sum("l_total", ("i_other", "i_leases", "j_bonds",
                                                 "k_trade")),)),
        ),
        gaps=MIX.gaps(),
        instant_concepts=BALANCE_CONCEPTS,
        instants=INSTANTS,
        sentences=(
            SentenceFigureSpec(
                "shares_outstanding", 181, "azioni ordinarie",
                r"suddiviso in numero (?P<amount>\d{1,3}(?:\.\d{3})+) azioni ordinarie", "2025",
                unit="shares",
                note="Acciones ordinarias de S.S. Lazio S.p.A. (nota 15 consolidada, pág. 181): "
                     "una sola clase; el grupo no tiene acciones propias (pág. 116)."),
        ),
    ),
)
