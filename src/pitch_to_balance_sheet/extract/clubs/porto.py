"""Futebol Clube do Porto - Futebol, SAD, 2024/25: Relatório Anual Integrado (versão não ESEF).

Decisión del usuario del 27/09/2026: la fuente son las cuentas consolidadas del PDF, descargado
a mano del visor de la CMVM. El ESEF no se ha podido descargar y queda fuera. El control es el
comunicado de resultados 2024/25 del portal de transparencia: las cifras que trae tienen que
coincidir, y las que no trae quedan sin control, anotado.

Texto directo con pdfplumber. Cada página del PDF lleva dos del informe: las tablas están en la
mitad derecha. En miles de euros ("montantes expressos em milhares de euros"), con punto de
miles, negativos entre paréntesis y la columna 30.06.2024 antes que la 30.06.2025:
- pág. 117 (232-233 del informe), Demonstração Consolidada dos Resultados por Naturezas. No
  tiene línea de total de ingresos ni de resultado financiero; el de traspasos y el financiero
  son totales sin rótulo.
- pág. 154 (307), nota 27, Custos com pessoal, en positivo; su total tiene que coincidir con la
  línea de la cuenta, cambiada de signo.
- pág. 152 (303), mitad derecha, nota 25: el detalle de las prestações de serviços, con el
  subtotal de receitas desportivas y el total sin rótulo (mapeo en config/line_items.yaml).
- pág. 156 (310), mitad izquierda, nota 28: amortizaciones, deterioro, ingresos y costes de
  traspasos y "Mais-valias com alienações de passes de jogadores".
- pág. 158 (315), nota 33, información por segmentos: el total de proveitos operacionais
  excluindo passes de jogadores con clientes externos, 149.540, es el de los ingresos (decisión
  del usuario del 27/09/2026). La cabecera "Outros serviços" ocupa dos líneas y la página no
  dice la unidad: la confirma el cuadre con las tres líneas de la cuenta, que sí la dice.

Fase 3b, balance al 30/06/2025:
- pág. 116 (230-231), Demonstração Consolidada da Posição Financeira: activo en la mitad
  izquierda y pasivo en la derecha.
- pág. 141, mitad derecha, nota 11: la antigüedad de los saldos de clientes, con las
  transações com passes de jogadores corrientes, en nominal (solo se usa la columna Total).
- pág. 148, mitad derecha, nota 21: fornecedores no corrientes y corrientes a 30.06.2025, con
  las transações de passes de jogadores, en nominal, y la actualización financiera del conjunto.
- acciones: pág. 145, nota 17 (22.500.000 acciones), y pág. 42, las 100 acciones propias.
El comunicado solo trae el balance resumido: los conceptos de balance quedan sin control.

Comunicado (control), en miles de euros, columnas 2023/2024 y 2024/2025 y, a la derecha,
variación y porcentaje, que se dejan fuera de la región:
- pág. 4: demonstração dos resultados resumida y desglose de los proveitos operacionais.
- pág. 5: desglose de los custos operacionais.
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
    Sum,
    TableSpec,
    TextCellSpec,
)

YEARS = ("2024", "2025")  # en el orden de las columnas
RIGHT_HALF = (0.5, 0.0, 1.0, 1.0)
LEFT_HALF = (0.0, 0.0, 0.5, 1.0)
BALANCE_HEADER = r"^30\.06\.202[45]$"
CURRENT_ASSETS = {
    "inventories": r"^inventarios$", "receivables": r"^clientes$",
    "other_debtors": r"^outros devedores correntes$", "other_assets": r"^outros ativos correntes$",
    "financial": r"^outros ativos financeiros$", "cash": r"^caixa e equivalentes de caixa$",
    "total": r"^total de ativos correntes$",
}
NONCURRENT_LIABILITIES = {
    "bonds": r"^emprestimos obrigacionistas$", "other_loans": r"^outros emprestimos$",
    "leases": r"^passivos de locacao$", "suppliers": r"^fornecedores$",
    "other": r"^outros passivos nao correntes$", "post_employment": r"^responsabilidades por",
    "deferred_tax": r"^passivos por impostos diferidos$", "provisions": r"^provisoes$",
    "total": r"^total de passivos nao correntes$",
}
CURRENT_LIABILITIES = {
    "bank": r"^emprestimos bancarios$", "bonds": r"^emprestimos obrigacionistas$",
    "other_loans": r"^outros emprestimos$", "leases": r"^passivos de locacao$",
    "other_creditors": r"^outros credores$", "suppliers": r"^fornecedores$",
    "other": r"^outros passivos correntes$", "total": r"^total de passivos correntes$",
}
SUPPLIERS_NONCURRENT = {
    "current_account": r"^fornecedores, conta corrente$",
    "transfers": r"^transacoes de passes de jogadores$",
    "discount": r"^atualizacao de dividas a terceiros$",
    # El total no tiene rótulo, pero el texto del PDF le pone el de una nota al pie que lo pisa.
    "total": r"^dragon notes$",
}
SUPPLIERS_CURRENT = {
    "current_account": r"^$", "transfers": r"^transacoes com passes de jogadores$",
    "discount": r"^atualizacao de dividas a terceiros$",
}
CUSTOMERS_AGEING = {
    "current_account": r"^clientes conta corrente\b",
    "transfers": r"^transacoes com passes de jogadores\b",
    "operations": r"^operacoes correntes\b",
}
BORROWINGS_NOTE = (
    "Empréstimos bancários, obrigacionistas y outros empréstimos (pág. 116, nota 19): los "
    "empréstitos obligacionistas (incluidas las Dragon Notes, 115.000) y el factoring de "
    "Sagasta, que el club presenta como outros empréstimos. Cuadra con la dívida financeira "
    "líquida del comunicado (pág. 7): 272.502 − 18.409 de caja = 254.093."
)
TRANSFER_NOTE = (
    "Transações com passes de jogadores (notas 11 y 21): los importes corrientes y los "
    "acreedores no corrientes van en nominal, sin la actualización financiera, que el informe "
    "da para el conjunto de clientes o fornecedores. Los deudores no corrientes son la línea "
    "clientes del balance (pág. 116): solo tiene transações com passes (5.700 en nominal, pág. "
    "142), así que es su valor actualizado."
)
PNL_ROWS = {
    "sales": r"^vendas$",
    "services": r"^prestacoes de servicos$",
    "other_income": r"^outros proveitos$",
    "cost_of_sales": r"^custo das vendas$",
    "external_supplies": r"^fornecimentos e servicos externos$",
    "staff": r"^custos com o pessoal$",
    "depreciation": r"^depreciacoes e amortizacoes, excluindo passes",
    "provisions": r"^provisoes e perdas por imparidade excluindo passes",
    "other_costs": r"^outros custos$",
    "operating_ex_players": r"^resultados operacionais excluindo resultados com passes",
    "player_amortisation": r"^amortizacoes e perdas por imparidade com passes",
    "player_income": r"^proveitos com transacoes de passes",
    "player_costs": r"^custos com transacoes de passes",
    "operating_result": r"^resultados operacionais$",
    "financial_costs": r"^custos e perdas financeiras$",
    "financial_income": r"^proveitos e ganhos financeiros$",
    "investments": r"^resultados relativos a investimentos$",
    "result_before_tax": r"^resultado antes de impostos$",
    "tax": r"^imposto sobre o rendimento$",
    "net_result": r"^resultado liquido consolidado do exercicio$",
    "attributable_parent": r"^detentores de capital proprio da empresa-mae$",
    "attributable_nci": r"^interesses que nao controlam$",
}
REVENUE_ROWS = ("sales", "services", "other_income")
SERVICES_ROWS = {
    "uefa": r"^premios competicoes uefa$",
    "fifa": r"^premios competicoes fifa$",
    "tickets": r"^receita de bilheteira$",
    "season_tickets": r"^receita de lugares anuais$",
    "other_sports": r"^outras receitas desportivas$",
    "advertising": r"^publicidade$",
    "broadcasting": r"^direitos de transmissoes$",
    "hospitality": r"^corporate hospitality$",
    "other_services": r"^outras prestacoes de servicos$",
}
SPORTS_ROWS = ("uefa", "fifa", "tickets", "season_tickets", "other_sports")
PLAYER_ROWS = {
    "amortisation": r"^amortizacoes de passes de jogadores$",
    "impairment": r"^perdas por imparidade com passes de jogadore ?s$",
    "disposal_income": r"^proveitos com alienacoes de passes de jogadores \(i\)$",
    "loan_income": r"^proveitos com emprestimos de jogadores$",
    "other_income": r"^outros proveitos com jogadores$",
    "disposal_costs": r"^custos com alienacoes de passes de jogadores \(ii\)$",
    "loan_costs": r"^custos com emprestimos de jogadores$",
    "other_costs": r"^outros custos com jogadores$",
    "disposal_gains": r"^mais-valias com alienacoes de passes de jogadores \(nota$",
}
MIX = mix.for_club("porto")
SEGMENT_COLUMNS = ("a", "b", "c", "other", "total")
SEGMENT_ROWS = {
    "external": r"^resultantes de operacoes com clientes externos$",
    "other_segments": r"^resultantes de operacoes com outros segmentos$",
}
STAFF_ROWS = {
    "board": r"^remuneracoes dos orgaos sociais$",
    "players_and_coaches": r"^remuneracoes dos atletas/tecnicos$",
    "employees": r"^remuneracoes do pessoal$",
    "pensions": r"^beneficios pos emprego",
    "social_charges": r"^encargos sobre remuneracoes$",
    "insurance": r"^seguros$",
    "severance": r"^indemnizacoes$",
    "other": r"^outros gastos com pessoal$",
}
REVENUE_NOTE = (
    "Total de proveitos operacionais excluindo proveitos com passes de jogadores con clientes "
    "externos, nota 33 (pág. 158); el comunicado da el mismo. La cuenta de resultados no tiene "
    "total: sus tres líneas (Vendas, Prestações de serviços y Outros proveitos) suman 149.541, "
    "un cuadre que pasa por redondeo."
)
REVENUE_EX_NOTE = (
    REVENUE_NOTE + " Los traspasos y las cesiones van aparte, en Proveitos com transações de "
    "passes de jogadores (nota 28, pág. 156: alienações, empréstimos y otros): no hay nada que "
    "restar."
)
SEVERANCE_NOTE = (
    "Indemnizações (nota 27, pág. 154): una fila ordinaria dentro del total de personal, sin "
    "clasificar como excepcional. Según la nota, sobre todo las de los jugadores Francisco "
    "Meixedo y Eric Pimentel y la del técnico Vítor Bruno y su equipo. Informativa: no ajusta "
    "ninguna métrica."
)
NET_NOTE = (
    "Resultado líquido consolidado do exercício, con los interesses que não controlam (1.748); "
    "atribuible a la matriz, 39.240 (net_result_attributable_parent)."
)
ATTRIBUTABLE_NOTE = (
    "Detentores de capital próprio da Empresa-Mãe (pág. 117): el resultado sin los interesses "
    "que não controlam. Informativa."
)

# Comunicado de resultados (control).
RELEASE_REGION = (0.0, 0.0, 0.775, 1.0)  # sin las columnas de variación y porcentaje
RELEASE_HEADER = r"^20\d\d/20\d\d$"
RELEASE_RESULTS = {
    "operating_income": r"^proveitos operacionais excluindo proveitos com passes$",
    "operating_costs": r"^custos operacionais excluindo custos com passes$",
    "operating_ex_players": r"^resultado operacional excluindo resultados com passes$",
    "player_amortisation": r"^amortizacoes e perdas por imparidade com passes$",
    "player_result": r"^resultado com cedencia de passes$",
    "operating_result": r"^resultado operacional$",
    "financial_result": r"^resultado financeiro$",
    "investments": r"^resultados relativos a investimentos$",
    "tax": r"^imposto sobre o rendimento$",
    "minorities": r"^interesses minoritarios$",
    "net_result_parent": r"^resultado consolidado do periodo$",
}
RELEASE_INCOME = {
    "merchandising": r"^merchandising$",
    "tickets": r"^bilheteira - bilhetes avulso$",
    "season_tickets": r"^bilheteira - lugares anuais$",
    "uefa": r"^provas uefa$",
    "fifa": r"^provas fifa \(cwc\)$",
    "other_sports": r"^outras receitas desportivas$",
    "broadcasting": r"^direitos de transmissao",
    "sponsorship": r"^publicidade e sponsorizacao",
    "other": r"^outros proveitos$",
    "total": r"^total$",
}
RELEASE_COSTS = {
    "cost_of_sales": r"^cmv$",
    "external_supplies": r"^fornecimentos e servicos externos$",
    "staff": r"^custos com pessoal$",
    "depreciation": r"^amortizacoes excluindo depreciacoes de passes$",
    "provisions": r"^provisoes e perdas por imparidade excluindo passes$",
    "other": r"^outros custos$",
    "total": r"^total$",
}
RELEASE_NET_NOTE = (
    "Resultado Consolidado do Período (atribuible a la matriz, 39.240) menos Interesses "
    "Minoritários (−1.748): el resultado consolidado total, 40.988, que el comunicado cita "
    "también en el texto (pág. 7)."
)

SPEC = ClubSpec(
    club_id="porto",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«montantes expressos em milhares de euros» en la pág. 117 y «milhares de "
               "Euros» en la 154 del informe, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        # En la pág. 116 el rótulo va en negrita y el texto del PDF duplica cada letra.
        unit_evidence=r"milhares de euros|mmiillhhaarreess ddee eeuurrooss",
        thousands=".",
        tables=(
            TableSpec(
                "pnl", 117, YEARS, PNL_ROWS, region=RIGHT_HALF, header=r"^30\.06\.202[45]$",
                totals_after={"player_result": "player_costs",
                              "financial_result": "investments"},
                sums=(
                    Sum("operating_ex_players", (*REVENUE_ROWS, "cost_of_sales",
                                                 "external_supplies", "staff", "depreciation",
                                                 "provisions", "other_costs")),
                    Sum("player_result", ("player_amortisation", "player_income",
                                          "player_costs")),
                    Sum("operating_result", ("operating_ex_players", "player_result")),
                    Sum("financial_result", ("financial_costs", "financial_income",
                                             "investments")),
                    Sum("result_before_tax", ("operating_result", "financial_result")),
                    Sum("net_result", ("result_before_tax", "tax")),
                    Sum("net_result", ("attributable_parent", "attributable_nci")),
                ),
            ),
            TableSpec(
                "segments", 158, SEGMENT_COLUMNS, SEGMENT_ROWS,
                region=(0.5, 0.37, 1.0, 0.47),  # solo el bloque de 30.06.2025
                header=r"^(A|B|C|servi\S+|Total)$", join_header_lines=True, unit_from="pnl",
                cross=(Cross("total", SEGMENT_COLUMNS[:-1], tuple(SEGMENT_ROWS)),),
            ),
            TableSpec(
                "services", 152, YEARS, SERVICES_ROWS, region=RIGHT_HALF,
                header=r"^30\.06\.202[45]$", select=SERVICES_ROWS["uefa"],
                totals_after={"sports": "other_sports", "total": "other_services"},
                sums=(Sum("sports", SPORTS_ROWS),
                      Sum("total", ("sports", "advertising", "broadcasting", "hospitality",
                                    "other_services"))),
            ),
            TableSpec(
                "players", 156, YEARS, PLAYER_ROWS, region=(0.0, 0.0, 0.5, 0.6),
                header=r"^30\.06\.202[45]$",
                totals_after={"amortisation_total": "impairment", "income": "other_income",
                              "costs": "other_costs", "result": "costs"},
                sums=(Sum("amortisation_total", ("amortisation", "impairment")),
                      Sum("income", ("disposal_income", "loan_income", "other_income")),
                      Sum("costs", ("disposal_costs", "loan_costs", "other_costs")),
                      Sum("result", ("amortisation_total", "income", "costs")),
                      Sum("disposal_gains", ("disposal_income", "disposal_costs"))),
            ),
            TableSpec(
                "staff", 154, YEARS, STAFF_ROWS, region=RIGHT_HALF, header=r"^30\.06\.202[45]$",
                select=STAFF_ROWS["severance"],
                totals_after={"staff_costs_total": "other"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
            # Fase 3b: balance y notas.
            TableSpec("bs_noncurrent_assets", 116, YEARS, {"receivables": r"^clientes$"},
                      region=LEFT_HALF, header=BALANCE_HEADER,
                      block=(r"^ativos nao correntes$", r"^total de ativos nao correntes$")),
            TableSpec("bs_current_assets", 116, YEARS, CURRENT_ASSETS, region=LEFT_HALF,
                      header=BALANCE_HEADER,
                      block=(r"^ativos correntes$", CURRENT_ASSETS["total"]),
                      sums=(Sum("total", tuple(CURRENT_ASSETS)[:-1]),)),
            TableSpec("bs_noncurrent_liabilities", 116, YEARS, NONCURRENT_LIABILITIES,
                      region=RIGHT_HALF, header=BALANCE_HEADER, select=r"^passivo nao corrente$",
                      block=(r"^passivo nao corrente$", NONCURRENT_LIABILITIES["total"]),
                      sums=(Sum("total", tuple(NONCURRENT_LIABILITIES)[:-1]),)),
            TableSpec("bs_current_liabilities", 116, YEARS, CURRENT_LIABILITIES,
                      region=RIGHT_HALF, header=BALANCE_HEADER, select=r"^passivo nao corrente$",
                      block=(r"^passivo corrente$", CURRENT_LIABILITIES["total"]),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)[:-1]),)),
            TableSpec("customers", 141, ("total", "up_to_90", "over_360"), CUSTOMERS_AGEING,
                      region=RIGHT_HALF, header=r"^(Total|dias)$",
                      header_label=r"^30\.06\.2025\b",
                      sums=(Sum("current_account", ("transfers", "operations"),
                                columns=("total",)),)),
            TableSpec("suppliers_noncurrent", 148,
                      ("total", "year_1", "year_2", "year_3", "year_4"), SUPPLIERS_NONCURRENT,
                      region=RIGHT_HALF, header=r"^(30\.06\.2025|ANOS?)$",
                      totals_after={"subtotal": "transfers"},
                      # La tabla sigue hasta el final de la página: solo el bloque no corriente.
                      block=(r"^fornecedores - nao corrente$", SUPPLIERS_NONCURRENT["total"]),
                      sums=(Sum("subtotal", ("current_account", "transfers")),
                            Sum("total", ("subtotal", "discount")))),
            TableSpec("suppliers_current", 148, ("total", "up_to_90", "up_to_180", "over_180"),
                      SUPPLIERS_CURRENT, region=RIGHT_HALF, header=r"^(30\.06\.2025|DIAS)$",
                      after={"current_account": r"^fornecedores, conta corrente$"},
                      totals_after={"subtotal": "transfers", "total": "discount"},
                      sums=(Sum("subtotal", ("current_account", "transfers")),
                            Sum("total", ("subtotal", "discount")))),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "staff", year), sign=-1)
              for year in YEARS),
            LinkSum(("segments", "external", "total"),
                    tuple(("pnl", row, "2025") for row in REVENUE_ROWS)),
            *(Link(("services", "total", year), ("pnl", "services", year)) for year in YEARS),
            *(Link(("players", key, year), ("pnl", line, year))
              for key, line in (("amortisation_total", "player_amortisation"),
                                ("income", "player_income"), ("costs", "player_costs"))
              for year in YEARS),
            MIX.check(),
            # Balance: las notas de fornecedores son sus líneas del balance.
            Link(("suppliers_noncurrent", "total", "total"),
                 ("bs_noncurrent_liabilities", "suppliers", "2025")),
            Link(("suppliers_current", "total", "total"),
                 ("bs_current_liabilities", "suppliers", "2025")),
        ),
        text_cells=(
            TextCellSpec("share_capital", "shares", 145, "ações nominativas e ordinárias",
                         r"composto por (?P<amount>\d{1,3}(?:\.\d{3})+) ações"),
            TextCellSpec("treasury", "shares", 42, "ações próprias",
                         r"detém (?P<amount>\d+) ações próprias, com valor contabilístico"),
        ),
        gaps=MIX.gaps(),
        figures=(
            FigureSpec("revenue_total_reported", (Part("segments", "external", "total"),),
                       "2025", note=REVENUE_NOTE),
            FigureSpec("revenue_ex_player_trading", (Part("segments", "external", "total"),),
                       "2025", note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("staff_severance_disclosed", (("staff", "severance"),), "2025",
                       note=SEVERANCE_NOTE, included_in_staff_costs="true"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025", note=NET_NOTE),
            FigureSpec("net_result_attributable_parent", (("pnl", "attributable_parent"),),
                       "2025", note=ATTRIBUTABLE_NOTE),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("players", "amortisation"),),
                       "2025", negate=True, note="Amortizações de passes de jogadores (nota 28)."),
            FigureSpec("impairment_player_registrations", (("players", "impairment"),), "2025",
                       negate=True,
                       note="Perdas por imparidade com passes de jogadores (nota 28)."),
            FigureSpec("profit_on_player_disposals", (("players", "disposal_gains"),), "2025",
                       note="Mais-valias com alienações de passes de jogadores (nota 28): "
                            "proveitos menos custos con alienações (i)+(ii). Fuera quedan "
                            "cesiones y otros."),
            FigureSpec("player_trading_other_income",
                       (("players", "loan_income"), ("players", "other_income")), "2025",
                       note="Proveitos com empréstimos de jogadores y outros proveitos com "
                            "jogadores (nota 28), fuera de las mais-valias."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Caixa e equivalentes de caixa (pág. 116, nota 15)."),
            *balance.split("borrowings",
                           (Part("bs_current_liabilities", "bank"),
                            Part("bs_current_liabilities", "bonds"),
                            Part("bs_current_liabilities", "other_loans")),
                           (Part("bs_noncurrent_liabilities", "bonds"),
                            Part("bs_noncurrent_liabilities", "other_loans")),
                           "2025", note=BORROWINGS_NOTE),
            *balance.split("lease_liabilities", Part("bs_current_liabilities", "leases"),
                           Part("bs_noncurrent_liabilities", "leases"), "2025",
                           note="Passivos de locação (pág. 116, nota 34)."),
            *balance.split("transfer_payables", Part("suppliers_current", "transfers", "total"),
                           Part("suppliers_noncurrent", "transfers", "total"), "2025",
                           note=TRANSFER_NOTE),
            *balance.split("transfer_receivables", Part("customers", "transfers", "total"),
                           Part("bs_noncurrent_assets", "receivables"), "2025",
                           note=TRANSFER_NOTE),
            FigureSpec("shares_outstanding", (Part("share_capital", "shares", "2025"),
                                              Part("treasury", "shares", "2025", sign=-1)),
                       "2025", unit="shares",
                       note="Acciones de la SAD (22.500.000, nota 17, pág. 145), de las "
                            "categorías A y B, menos las 100 acciones propias que tiene la "
                            "PortoSeguro (pág. 42)."),
        ),
    ),
    controls=(DocumentSpec(
        method="text",
        unit_evidence=r"valores em milhares de euros",
        thousands=".",
        control_index=0,
        tables=(
            TableSpec(
                "results", 4, YEARS, RELEASE_RESULTS, region=RELEASE_REGION,
                header=RELEASE_HEADER, header_label=r"^demonstracoes de resultados$",
                sums=(
                    Sum("operating_ex_players", ("operating_income", "operating_costs")),
                    Sum("operating_result", ("operating_ex_players", "player_amortisation",
                                             "player_result")),
                    Sum("net_result_parent", ("operating_result", "financial_result",
                                              "investments", "tax", "minorities")),
                ),
            ),
            TableSpec(
                "income", 4, YEARS, RELEASE_INCOME, region=RELEASE_REGION,
                header=RELEASE_HEADER,
                header_label=r"^proveitos operacionais excluindo proveitos com passes$",
                sums=(Sum("total", tuple(RELEASE_INCOME)[:-1]),),
            ),
            TableSpec(
                "costs", 5, YEARS, RELEASE_COSTS, region=RELEASE_REGION,
                header=RELEASE_HEADER,
                header_label=r"^custos operacionais excluindo custos com passes$",
                sums=(Sum("total", tuple(RELEASE_COSTS)[:-1]),),
            ),
        ),
        links=(
            *(Link(("income", "total", year), ("results", "operating_income", year))
              for year in YEARS),
            *(Link(("costs", "total", year), ("results", "operating_costs", year), sign=-1)
              for year in YEARS),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("results", "operating_income"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("results", "operating_income"),),
                       "2025"),
            FigureSpec("staff_costs", (("costs", "staff"),), "2025"),
            FigureSpec("net_result", (Part("results", "net_result_parent"),
                                      Part("results", "minorities", sign=-1)), "2025",
                       note=RELEASE_NET_NOTE),
            FigureSpec("net_result_attributable_parent", (("results", "net_result_parent"),),
                       "2025"),
            # El mismo criterio sobre las partidas del comunicado (pág. 4).
            FigureSpec("revenue_broadcasting",
                       (("income", "uefa"), ("income", "fifa"), ("income", "broadcasting")),
                       "2025", note="Provas UEFA + Provas FIFA + Direitos de Transmissão."),
            FigureSpec("revenue_other", (("income", "other_sports"), ("income", "other")), "2025",
                       note="Outras Receitas Desportivas + Outros Proveitos."),
        ),
        without={
            "staff_severance_disclosed": "el comunicado no desglosa los gastos de personal",
            "revenue_matchday": "el comunicado suma Corporate Hospitality (matchday) a "
                                "Publicidade e Sponsorização",
            "revenue_commercial": "el comunicado suma Corporate Hospitality (matchday) a "
                                  "Publicidade e Sponsorização",
            "player_trading_other_income": "el comunicado da el resultado con cedência de "
                                           "passes, sin desglose",
            "amortisation_player_registrations": "el comunicado da amortización y deterioro "
                                                 "juntos (34.377)",
            "impairment_player_registrations": "el comunicado da amortización y deterioro "
                                               "juntos (34.377)",
            "profit_on_player_disposals": "el comunicado da el resultado con cedência de passes "
                                          "(100.436), que incluye cesiones y otros, no las "
                                          "mais-valias",
            **dict.fromkeys(
                (*(f"{concept}{suffix}" for concept in ("borrowings", "lease_liabilities",
                                                        "transfer_payables",
                                                        "transfer_receivables")
                   for suffix in ("", "_current", "_non_current")),
                 "cash", "shares_outstanding"),
                "el comunicado solo trae el balance resumido por bloques (pág. 7) y la dívida "
                "financeira líquida, 254.093, que es borrowings menos cash"),
        },
    ),),
)
