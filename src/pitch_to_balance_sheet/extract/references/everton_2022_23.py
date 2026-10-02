"""Everton Football Club Company Limited (00036624), cuentas del grupo a 30/06/2023 de Companies
House: escaneo, OCR. Ejercicio de referencia de la compra de 2024 (las de 2023/24 se depositaron
el 02/04/2025, después del anuncio).

Páginas localizadas a mano en el OCR guardado y en la página renderizada:
- pág. 13, Consolidated profit and loss account: seis columnas en £'000 (operaciones,
  jugadores y total de 2023 y de 2022 reexpresado). En Turnover la columna de jugadores es un
  guion.
- pág. 14, Consolidated balance sheet: dos columnas por año, las partidas en la interior y los
  subtotales en la exterior.
- pág. 30, nota 15, y pág. 31, nota 16: acreedores a menos y a más de un año (grupo y
  sociedad), y el desglose de los préstamos (Other loans) por vencimiento. Los préstamos
  devengan interés: el CLBILS «incurs a market value rate of interest» (pág. 31) y el préstamo
  del accionista mayoritario de 22,5 millones, dentro de loans, es «interest bearing» (nota 21,
  pág. 33).
- pág. 32, nota 18: el préstamo sin interés de 450.751 de Bluesky Capital (de Farhad Moshiri) no
  tiene fecha de devolución y va en el patrimonio (other reserves, FRS 102.22): no es pasivo ni
  deuda.
FRS 102: sin pasivos por arrendamiento en las notas 15 y 16.
"""

from pitch_to_balance_sheet.extract import balance
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
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

PNL_COLUMNS = ("operations_2023", "players_2023", "total_2023",
               "operations_2022", "players_2022", "total_2022")
# El OCR desordena los rótulos en dos líneas ("exceptional costs Operating expenses -"): los
# patrones buscan una parte del rótulo.
PNL_ROWS = {
    "turnover": r"^turnover$",
    "operating_expenses": r"^operating expenses$",
    "exceptional": r"exceptional costs",
    "operating_loss": r"^operating loss$",
}
BALANCE_COLUMNS = ("inner_2023", "outer_2023", "inner_2022", "outer_2022")
BALANCE_ROWS = {
    "debtors_current": r"^- due within one year$",
    "debtors_noncurrent": r"^- due after one year$",
    "cash": r"^cash at bank and in hand$",
    "creditors_current": r"^creditors- amounts falling due within one year$",
    "creditors_noncurrent": r"creditors - amounts falling due after more$",
}
GROUP_COMPANY = ("group_2023", "group_2022", "company_2023", "company_2022")
GROUP = GROUP_COMPANY[:2]
CREDITORS_CURRENT = {
    "other_loans": r"^other loans \(note 16\)$",
    "trade": r"^trade creditors$",
    "accruals": r"^accruals and deferred income$",
    "tax": r"^social security and other taxes$",
}
CREDITORS_NONCURRENT = {
    "other_loans": r"^other loans \(see borrowings below\)$",
    "trade": r"^trade creditors$",
    "accruals": r"^accruals and deferred income$",
}
BORROWINGS_COLUMNS = ("loans_2023", "loans_2022", "total_2023", "total_2022")
BORROWINGS_ROWS = {"within_one_year": r"^within one year$",
                   "one_to_five_years": r"^between one and five years$"}

REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 13) separa la columna de jugadores (player and management "
    "trading), y en Turnover esa columna es un guion: no hay traspasos ni cesiones en los "
    "ingresos."
)
BORROWINGS_NOTE = (
    "Other loans (notas 15 y 16, págs. 30 y 31), con interés: el CLBILS de 11,25 millones a "
    "tipo de mercado (pág. 31) y el préstamo con interés de 22,5 millones del accionista "
    "mayoritario (nota 21, pág. 33). El préstamo sin interés de 450.751 de Bluesky Capital va en "
    "el patrimonio (nota 18, pág. 32): no entra."
)

SPEC = ClubSpec(
    club_id="everton",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 13, 14, 30 y 31, vistas en la página renderizada. "
               "El OCR lee la £ como € o $: la moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 13, PNL_COLUMNS, PNL_ROWS,
                totals_after={"operating_costs": "exceptional"},
                sums=(Sum("operating_costs", ("operating_expenses", "exceptional")),
                      Sum("operating_loss", ("turnover", "operating_costs"))),
                cross=(Cross("total_2023", ("operations_2023", "players_2023"),
                             tuple(PNL_ROWS) + ("operating_costs",)),),
            ),
            TableSpec("bs", 14, BALANCE_COLUMNS, BALANCE_ROWS,
                      totals_after={"current_assets": "cash"},
                      sums=(Sum("current_assets", ("debtors_current", "debtors_noncurrent",
                                                   "cash"), ("inner_2023", "inner_2022")),)),
            TableSpec("creditors_current", 30, GROUP_COMPANY, CREDITORS_CURRENT,
                      select=CREDITORS_CURRENT["other_loans"],
                      totals_after={"total": "tax"},
                      sums=(Sum("total", tuple(CREDITORS_CURRENT), GROUP),)),
            TableSpec("creditors_noncurrent", 31, GROUP_COMPANY, CREDITORS_NONCURRENT,
                      select=CREDITORS_NONCURRENT["other_loans"],
                      totals_after={"total": "accruals"},
                      sums=(Sum("total", tuple(CREDITORS_NONCURRENT), GROUP),)),
            # Desglose de los préstamos del grupo: su tabla acaba en el título de la de la
            # sociedad, que así la distingue. El total de la columna Other loans de 2023, en
            # negrita, el OCR lo lee 349,385 donde la imagen dice 341,385: el cuadre va en las
            # columnas Total.
            TableSpec("borrowings", 31, BORROWINGS_COLUMNS, BORROWINGS_ROWS,
                      select=r"^company other loans total$",
                      totals_after={"total": "one_to_five_years"},
                      sums=(Sum("total", tuple(BORROWINGS_ROWS), ("total_2023", "total_2022")),)),
        ),
        links=(
            Link(("creditors_current", "total", "group_2023"),
                 ("bs", "creditors_current", "inner_2023"), sign=-1),
            Link(("creditors_noncurrent", "total", "group_2023"),
                 ("bs", "creditors_noncurrent", "outer_2023"), sign=-1),
            LinkSum(("borrowings", "total", "total_2023"),
                    (("creditors_current", "other_loans", "group_2023"),
                     ("creditors_noncurrent", "other_loans", "group_2023"))),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "turnover"),), "total_2023"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "turnover"),), "total_2023",
                       note=REVENUE_EX_NOTE),
            FigureSpec("cash", (("bs", "cash", "inner_2023"),), "inner_2023",
                       note="Cash at bank and in hand (pág. 14)."),
            *balance.split("borrowings", Part("creditors_current", "other_loans"),
                           Part("creditors_noncurrent", "other_loans"), "group_2023",
                           note=BORROWINGS_NOTE),
        ),
    ),
)
