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
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    DocumentSpec,
    FigureSpec,
    Link,
    LinkSum,
    Sum,
    TableSpec,
)

YEARS = ("2025", "2024")
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
        ),
        gaps=MIX.gaps(),
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
        ),
    ),
)
