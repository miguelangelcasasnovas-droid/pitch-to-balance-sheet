"""Sport Lisboa e Benfica - Futebol, SAD, 2024/25: Relatório e Contas, en portugués. Con texto.

El informe trae las cuentas IFRS de la propia SAD (nota 1 y nota 2.2), sin estados consolidados.
Texto directo con pdfplumber. Las cifras van en miles de euros ("valores em milhares de euros"),
con punto de miles y negativos entre paréntesis. Páginas localizadas buscando los títulos:
- pág. 118, Demonstração dos resultados, 30.06.25 y 30.06.24. Los totales de ingresos y de
  gastos operativos no llevan rótulo.
- pág. 159, nota 18, gastos com pessoal, en positivo. Tiene rótulos repetidos (remunerações
  fijas y variables de los órganos sociales y del personal), así que sus filas se identifican
  por su orden, con anclas. Su total tiene que coincidir con la línea de la cuenta de
  resultados, cambiada de signo.
Fase 3a:
- las partidas de ingresos son las tres líneas de la cuenta (mapeo en config/line_items.yaml);
- pág. 162, nota 20: "Resultado com alienações de direitos de atletas" (plusvalías menos
  minusvalías y comisiones) y el resto hasta el resultado de transacciones de la cuenta;
- pág. 165, nota 21: amortizaciones y pérdidas por deterioro de derechos de atletas.

Fase 3b, balance al 30/06/2025:
- pág. 117, Demonstração da posição financeira.
- pág. 146, nota 7 (clientes e outros devedores), pág. 152, nota 12 (empréstimos obtidos),
  pág. 154, nota 13 (fornecedores e outros credores), y pág. 155, nota 14 (outros passivos, con
  la cesión de créditos), no corrientes y corrientes.
- pág. 151, nota 11: el número de acciones (categorías A y B). La SAD no tiene acciones propias
  (pág. 47).
"""

from pitch_to_balance_sheet.extract import balance, mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    LinkSum,
    Part,
    Sum,
    TableSpec,
)

YEARS = ("2025", "2024")
CURRENT_ASSETS = {"receivables": r"^clientes e outros devedores$", "other": r"^outros ativos$",
                  "cash": r"^caixa e equivalentes de caixa$",
                  "total": r"^total do ativo corrente$"}
NONCURRENT_LIABILITIES = {
    "provisions": r"^provisoes$", "post_employment": r"^responsabilidades por beneficios",
    "loans": r"^emprestimos obtidos$", "payables": r"^fornecedores e outros credores$",
    "other": r"^outros passivos$", "total": r"^total do passivo nao corrente$",
}
CURRENT_LIABILITIES = {
    "loans": r"^emprestimos obtidos$", "payables": r"^fornecedores e outros credores$",
    "other": r"^outros passivos$", "total": r"^total do passivo corrente$",
}
LOANS_NONCURRENT = {
    "novo_banco": r"^novo banco$", "olb": r"^olb bank$",
    "bond_2022": r"^benfica sad 2022-2025$", "bond_2023": r"^benfica sad 2023-2026$",
    "bond_2024": r"^benfica sad 2024-2027$", "bond_2025": r"^benfica sad 2025-2029$",
}
LOANS_CURRENT = {"novo_banco": r"^novo banco$", "montepio": r"^montepio$", "olb": r"^olb bank$",
                 "bond_2021": r"^benfica sad 2021-2024$", "bond_2023": r"^benfica sad 2023-2026$",
                 "interest": r"^acrescimos de gastos - juros$"}
RECEIVABLES_CURRENT = {
    "athletes": r"^direitos de atletas$", "television": r"^direitos de televisao$",
    "matches": r"^receitas de jogos$", "commercial": r"^atividades comerciais$",
    "group": r"^empresas do grupo e partes relacionadas$", "sundry": r"^devedores diversos$",
    "doubtful": r"^clientes e outros devedores de cobranca duvidosa$",
    "discount": r"^atualizacao de dividas de terceiros$", "impairment": r"^imparidade de creditos$",
}
PAYABLES_CURRENT = {
    "clubs": r"^clubes e sociedades relacionadas com o futebol$",
    "current_activities": r"^atividades correntes$", "investments": r"^investimentos em ativos$",
    "group": r"^empresas do grupo e partes relacionadas$",
    "other": r"^outros credores e operacoes diversas$",
    "discount": r"^atualizacao de dividas de terceiros$",
}
OTHER_LIABILITIES_CURRENT = {
    "assignment": r"^cedencia de creditos$", "customer_advances": r"^adiantamento a clientes$",
    "sales_advances": r"^adiantamentos por conta de vendas$",
    "state": r"^estado e outros entes publicos$", "wages": r"^remuneracoes a liquidar$",
    "accruals": r"^acrescimos de gastos$", "television": r"^direitos de televisao$",
    "matches": r"^receitas de jogos$", "commercial": r"^atividades comerciais$",
}
BORROWINGS_NOTE = (
    "Empréstimos obtidos (pág. 117, nota 12): préstamos bancarios y empréstitos obligacionistas, "
    "con los intereses devengados (1.301); más la cesión de créditos de la nota 14 (22.078, a "
    "menos de un año; a más de un año, un guion): la cesión parcial y sin recurso de créditos "
    "futuros del contrato de derechos de televisión con NOS (pág. 156), igual que el factoring "
    "de Juventus y Porto (decisión del usuario del 29/09/2026)."
)
LEASE_GAP = (
    "no se publica: el balance (pág. 117) y las notas 12 a 14 no tienen ninguna línea de pasivos "
    "por arrendamiento. El derecho de uso del estadio (nota 4) es con Benfica Estádio, sociedad "
    "del grupo (nota 26), y el estado de flujos solo da 28 miles pagados por «Contrato de "
    "locação»; si hay un pasivo, va dentro de otra línea"
)
TRANSFER_NOTE = (
    "Direitos de atletas / clubes e sociedades relacionadas com o futebol (notas 7 y 13). La "
    "parte no corriente va neta de su actualización financiera (la única partida del bloque); "
    "la corriente, en nominal: su actualización e imparidad son del conjunto de la rúbrica."
)
HEADER = r"^30\.06\.2[45]$"
PNL_ROWS = {
    "tv_rights": r"^direitos de televisao$",
    "commercial": r"^atividades comerciais",
    "matchday": r"^receitas de jogos$",
    "supplies_and_services": r"^fornecimentos e servicos externos",
    "royalties": r"^royalties marca benfica$",
    "staff": r"^gastos com pessoal",
    "depreciation": r"^depreciacoes/amortizacoes",
    "provisions": r"^provisoes/imparidades",
    "other_costs": r"^outros gastos e perdas operacionais",
    "operating_result_ex_player_rights": r"^resultado operacional sem direitos de atletas$",
    "player_rights_income": r"^rendimentos com transacoes de direitos de atletas$",
    "player_rights_expenses": r"^gastos com transacoes de direitos de atletas$",
    "player_rights_amortisation": r"^amortizacoes e perdas de imparidade de direitos de atletas$",
    "operating_result": r"^resultado operacional$",
    "financial_income": r"^rendimentos e ganhos financeiros$",
    "financial_expenses": r"^gastos e perdas financeiros$",
    "financial_result": r"^resultado financeiro$",
    "result_before_tax": r"^resultado antes de imposto$",
    "tax": r"^imposto sobre o rendimento$",
    "net_result": r"^resultado liquido do periodo$",
}
COSTS = ("supplies_and_services", "royalties", "staff", "depreciation", "provisions",
         "other_costs")
STAFF_ORDER = (
    "board_fixed", "board_variable", "staff_fixed", "staff_variable", "severance",
    "post_employment", "social_charges", "work_accident_insurance", "related_parties",
    "other_staff_costs", "staff_costs_total",
)
STAFF_ANCHORS = {
    "board_fixed": r"^remuneracoes fixas$",
    "severance": r"^indemnizacoes$",
    "other_staff_costs": r"^outros gastos com pessoal$",
    "staff_costs_total": r"^$",
}
TRANSACTION_ROWS = {
    "gains": r"^ganhos com alienacoes de direitos de atletas \(mais-valias\)$",
    "losses": r"^perdas com alienacoes de direitos de atletas \(menos-valias\)$",
    "commissions": r"^gastos associados a alienacoes de direitos de atletas \(comissoes\)$",
    "result_disposals": r"^resultado com alienacoes de direitos de atletas$",
    "other_income": r"^outros rendimentos com transacoes de direitos de atletas$",
    "write_offs": r"^abates de direitos de atletas$",
    "other_costs": r"^outros gastos com transacoes de direitos de atletas$",
    "result_transactions": r"^resultado com transacoes de direitos de atletas$",
}
AMORTISATION_ROWS = {
    "amortisation": r"^amortizacoes de direitos de atletas$",
    "impairment": r"^perdas de imparidade de direitos de atletas$",
}
MIX = mix.for_club("benfica")
SEVERANCE_NOTE = (
    "Indemnizações (nota 18, pág. 159): una fila ordinaria dentro del total de personal, sin "
    "clasificar como excepcional. Informativa: no ajusta ninguna métrica."
)
REVENUE_EX_NOTE = (
    "La nota 15 (pág. 157) desglosa los ingresos operativos en direitos de televisão, "
    "atividades comerciais y receitas de jogos; los traspasos van aparte, en transações de "
    "direitos de atletas (nota 20): no hay traspasos ni cesiones en los ingresos."
)

SPEC = ClubSpec(
    club_id="benfica",
    currency="EUR",
    unit="thousands",
    multiplier=1000,
    unit_basis="«valores em milhares de euros» en las págs. 118 y 159, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"milhares de euros",
        thousands=".",
        tables=(
            TableSpec(
                "pnl", 118, YEARS, PNL_ROWS, header=HEADER,
                totals_after={"operating_revenue": "matchday",
                              "operating_costs": "other_costs"},
                sums=(
                    Sum("operating_revenue", ("tv_rights", "commercial", "matchday")),
                    Sum("operating_costs", COSTS),
                    Sum("operating_result_ex_player_rights", ("operating_revenue",
                                                              "operating_costs")),
                    Sum("operating_result", ("operating_result_ex_player_rights",
                                             "player_rights_income", "player_rights_expenses",
                                             "player_rights_amortisation")),
                    Sum("financial_result", ("financial_income", "financial_expenses")),
                    Sum("result_before_tax", ("operating_result", "financial_result")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
            ),
            TableSpec(
                "staff", 159, YEARS, {}, header=HEADER,
                rows_by_order=STAFF_ORDER, anchors=STAFF_ANCHORS,
                sums=(Sum("staff_costs_total", STAFF_ORDER[:-1]),),
            ),
            TableSpec(
                "transactions", 162, YEARS, TRANSACTION_ROWS, header=HEADER,
                select=TRANSACTION_ROWS["other_income"],
                sums=(Sum("result_disposals", ("gains", "losses", "commissions")),
                      Sum("result_transactions", ("result_disposals", "other_income",
                                                  "write_offs", "other_costs"))),
            ),
            TableSpec(
                "amortisation", 165, YEARS, AMORTISATION_ROWS, header=HEADER,
                select=AMORTISATION_ROWS["impairment"],
                totals_after={"total": "impairment"},
                sums=(Sum("total", tuple(AMORTISATION_ROWS)),),
            ),
            # Fase 3b: balance y notas.
            TableSpec("bs_noncurrent_assets", 117, YEARS,
                      {"receivables": r"^clientes e outros devedores$"}, header=HEADER,
                      block=(r"^ativo$", r"^total do ativo nao corrente$")),
            TableSpec("bs_current_assets", 117, YEARS, CURRENT_ASSETS, header=HEADER,
                      block=(r"^total do ativo nao corrente$", r"^total do ativo corrente$"),
                      sums=(Sum("total", ("receivables", "other", "cash")),)),
            TableSpec("bs_noncurrent_liabilities", 117, YEARS, NONCURRENT_LIABILITIES,
                      header=HEADER, block=(r"^passivo$", r"^total do passivo nao corrente$"),
                      sums=(Sum("total", tuple(NONCURRENT_LIABILITIES)[:-1]),)),
            TableSpec("bs_current_liabilities", 117, YEARS, CURRENT_LIABILITIES, header=HEADER,
                      block=(r"^total do passivo nao corrente$", r"^total do passivo corrente$"),
                      sums=(Sum("total", tuple(CURRENT_LIABILITIES)[:-1]),)),
            TableSpec("loans_noncurrent", 152, YEARS, LOANS_NONCURRENT, header=HEADER,
                      totals_after={"total": "bond_2025"},
                      block=(r"^emprestimos obtidos - nao corrente$",
                             r"^emprestimos obtidos - corrente$"),
                      sums=(Sum("total", tuple(LOANS_NONCURRENT)),)),
            TableSpec("loans_current", 152, YEARS, LOANS_CURRENT, header=HEADER,
                      totals_after={"total": "interest"},
                      block=(r"^emprestimos obtidos - corrente$", r"^valores em milhares"),
                      sums=(Sum("total", tuple(LOANS_CURRENT)),)),
            TableSpec("receivables_noncurrent", 146, YEARS,
                      {"athletes": r"^direitos de atletas$",
                       "discount": r"^atualizacao de dividas de terceiros$"},
                      header=HEADER, totals_after={"total": "discount"},
                      block=(r"^clientes e outros devedores - nao corrente$",
                             r"^clientes e outros devedores - corrente$"),
                      sums=(Sum("total", ("athletes", "discount")),)),
            TableSpec("receivables_current", 146, YEARS, RECEIVABLES_CURRENT, header=HEADER,
                      totals_after={"total": "impairment"},
                      block=(r"^clientes e outros devedores - corrente$",
                             r"^valores em milhares"),
                      sums=(Sum("total", tuple(RECEIVABLES_CURRENT)),)),
            TableSpec("payables_noncurrent", 154, YEARS,
                      {"clubs": r"^clubes e sociedades relacionadas com o futebol$",
                       "discount": r"^atualizacao de dividas de terceiros$"},
                      header=HEADER, totals_after={"total": "discount"},
                      block=(r"^fornecedores e outros credores - nao corrente$",
                             r"^fornecedores e outros credores - corrente$"),
                      sums=(Sum("total", ("clubs", "discount")),)),
            TableSpec("payables_current", 154, YEARS, PAYABLES_CURRENT, header=HEADER,
                      totals_after={"total": "discount"},
                      block=(r"^fornecedores e outros credores - corrente$",
                             r"^valores em milhares"),
                      sums=(Sum("total", tuple(PAYABLES_CURRENT)),)),
            TableSpec("equity", 151, YEARS, {"shares": r"^numero de acoes$"}, header=HEADER,
                      select=r"^numero de acoes$"),
            TableSpec("other_liabilities_noncurrent", 155, YEARS,
                      {"assignment": r"^cedencia de creditos$"}, header=HEADER,
                      select=r"^adiantamentos por conta de vendas$",
                      totals_after={"total": "assignment"},
                      block=(r"^outros passivos - nao corrente$", r"^outros passivos - corrente$"),
                      sums=(Sum("total", ("assignment",)),)),
            TableSpec("other_liabilities_current", 155, YEARS, OTHER_LIABILITIES_CURRENT,
                      header=HEADER, select=r"^adiantamentos por conta de vendas$",
                      totals_after={"total": "commercial"},
                      block=(r"^outros passivos - corrente$", r"^valores em milhares"),
                      sums=(Sum("total", tuple(OTHER_LIABILITIES_CURRENT)),)),
        ),
        links=(
            *(Link(("staff", "staff_costs_total", year), ("pnl", "staff", year), sign=-1)
              for year in YEARS),
            *(LinkSum(("transactions", "result_transactions", year),
                      (("pnl", "player_rights_income", year),
                       ("pnl", "player_rights_expenses", year))) for year in YEARS),
            *(Link(("amortisation", "total", year), ("pnl", "player_rights_amortisation", year),
                   sign=-1) for year in YEARS),
            MIX.check(),
            # Balance: cada nota es su línea del balance.
            *(Link((note, "total", year), (table, line, year))
              for note, table, line in (
                  ("loans_noncurrent", "bs_noncurrent_liabilities", "loans"),
                  ("loans_current", "bs_current_liabilities", "loans"),
                  ("receivables_noncurrent", "bs_noncurrent_assets", "receivables"),
                  ("receivables_current", "bs_current_assets", "receivables"),
                  ("payables_noncurrent", "bs_noncurrent_liabilities", "payables"),
                  ("payables_current", "bs_current_liabilities", "payables"),
                  ("other_liabilities_noncurrent", "bs_noncurrent_liabilities", "other"),
                  ("other_liabilities_current", "bs_current_liabilities", "other"))
              for year in YEARS),
        ),
        gaps={**MIX.gaps(), **balance.gaps("lease_liabilities", LEASE_GAP)},
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "operating_revenue"),), "2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "operating_revenue"),), "2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("staff_severance_disclosed", (("staff", "severance"),), "2025",
                       note=SEVERANCE_NOTE, included_in_staff_costs="true"),
            FigureSpec("net_result", (("pnl", "net_result"),), "2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations", (("amortisation", "amortisation"),),
                       "2025", note="Amortizações de direitos de atletas (nota 21)."),
            FigureSpec("impairment_player_registrations", (("amortisation", "impairment"),),
                       "2025", note="Perdas de imparidade de direitos de atletas (nota 21)."),
            FigureSpec("profit_on_player_disposals", (("transactions", "result_disposals"),),
                       "2025", note="Resultado com alienações de direitos de atletas (nota 20): "
                                    "plusvalías menos minusvalías y comisiones de venta."),
            FigureSpec("player_trading_other_income", (("transactions", "other_income"),),
                       "2025", note="Outros rendimentos com transações de direitos de atletas "
                                    "(nota 20), fuera del resultado com alienações."),
            # Balance al 30/06/2025.
            FigureSpec("cash", (("bs_current_assets", "cash"),), "2025",
                       note="Caixa e equivalentes de caixa (pág. 117, nota 10)."),
            *balance.split("borrowings",
                           (Part("bs_current_liabilities", "loans"),
                            Part("other_liabilities_current", "assignment")),
                           (Part("bs_noncurrent_liabilities", "loans"),
                            Part("other_liabilities_noncurrent", "assignment")), "2025",
                           note=BORROWINGS_NOTE),
            *balance.split("transfer_payables", Part("payables_current", "clubs"),
                           (Part("payables_noncurrent", "clubs"),
                            Part("payables_noncurrent", "discount")), "2025",
                           note=TRANSFER_NOTE),
            *balance.split("transfer_receivables", Part("receivables_current", "athletes"),
                           (Part("receivables_noncurrent", "athletes"),
                            Part("receivables_noncurrent", "discount")), "2025",
                           note=TRANSFER_NOTE),
            FigureSpec("shares_outstanding", (("equity", "shares"),), "2025", unit="shares",
                       note="Número de ações (nota 11): 23.000.000, de las categorías A (del "
                            "Sport Lisboa e Benfica) y B. La SAD no tiene acciones propias "
                            "(pág. 47)."),
        ),
    ),
)
