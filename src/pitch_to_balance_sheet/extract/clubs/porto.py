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
- pág. 158 (315), nota 33, información por segmentos: el total de proveitos operacionais
  excluindo passes de jogadores con clientes externos, 149.540, es el de los ingresos (decisión
  del usuario del 27/09/2026). La cabecera "Outros serviços" ocupa dos líneas y la página no
  dice la unidad: la confirma el cuadre con las tres líneas de la cuenta, que sí la dice.

Comunicado (control), en miles de euros, columnas 2023/2024 y 2024/2025 y, a la derecha,
variación y porcentaje, que se dejan fuera de la región:
- pág. 4: demonstração dos resultados resumida y desglose de los proveitos operacionais.
- pág. 5: desglose de los custos operacionais.
"""

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
)

YEARS = ("2024", "2025")  # en el orden de las columnas
RIGHT_HALF = (0.5, 0.0, 1.0, 1.0)
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
        unit_evidence=r"milhares de euros",
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
                "staff", 154, YEARS, STAFF_ROWS, region=RIGHT_HALF, header=r"^30\.06\.202[45]$",
                select=STAFF_ROWS["severance"],
                totals_after={"staff_costs_total": "other"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "staff", year), sign=-1)
              for year in YEARS),
            LinkSum(("segments", "external", "total"),
                    tuple(("pnl", row, "2025") for row in REVENUE_ROWS)),
        ),
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
        ),
        without={"staff_severance_disclosed": "el comunicado no desglosa los gastos de "
                                              "personal"},
    ),),
)
