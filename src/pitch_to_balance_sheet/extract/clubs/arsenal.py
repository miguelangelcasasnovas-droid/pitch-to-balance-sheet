"""Arsenal Holdings Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

Páginas localizadas a mano mirando la página renderizada:
- pág. 23, Consolidated profit and loss account: seis columnas en £'000 (operaciones sin
  traspasos, traspasos y total, de 2025 y de 2024). De "Net finance charges" hacia abajo solo
  hay cifras en las columnas de total: esas filas se cuadran solo ahí. El OCR se hace sobre la
  región de la tabla.
- pág. 34, nota 6, Employees: "Staff costs", 2025 y 2024 en £'000.

"Group turnover" incluye en la columna de traspasos 454 de "player trading", que según la nota
de la propia página son sobre todo ingresos por cesiones.
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Sum,
    TableSpec,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025",
               "operations_2024", "players_2024", "total_2024")
TOTALS = ("total_2025", "total_2024")
PNL_ROWS = {
    # "Turnover of the Group including its share of" / "joint ventures": las cifras van en la
    # segunda línea del rótulo.
    "turnover_including_jv": r"^joint ventures$",
    "share_of_jv_turnover": r"^share of turnover of joint venture$",
    "group_turnover": r"^group turnover$",
    "operating_expenses": r"^operating expenses$",
    "operating_result": r"^operating profit/\(loss\)$",
    "share_of_jv_operating_loss": r"^share of joint venture operating loss$",
    "profit_disposal_players": r"^profit on disposal of player registrations$",
    "result_before_finance": r"^profit/\(loss\) before net finance charges$",
    "net_finance_charges": r"^net finance charges$",
    "result_before_tax": r"^\(loss\) before taxation$",
    "tax": r"^tax on loss$",
    "net_result": r"^\(loss\) for the financial year$",
}
CROSS_ROWS = tuple(PNL_ROWS)[:8]
# La tabla de la pág. 23, de las cabeceras a "(Loss) for the financial year". Con la página
# entera, el OCR solo lee 16 de sus cifras; con esta región, todas.
PNL_REGION = (0.10, 0.15, 0.99, 0.50)
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
}

SPEC = ClubSpec(
    club_id="arsenal",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 23 y 34, vistas en la página renderizada. El OCR "
               "lee la £ como €, $, 2 o ·: la moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 23, PNL_COLUMNS, PNL_ROWS, region=PNL_REGION,
                sums=(
                    Sum("group_turnover", ("turnover_including_jv", "share_of_jv_turnover")),
                    Sum("operating_result", ("group_turnover", "operating_expenses")),
                    Sum("result_before_finance", ("operating_result",
                                                  "share_of_jv_operating_loss",
                                                  "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_finance", "net_finance_charges"),
                        TOTALS),
                    Sum("net_result", ("result_before_tax", "tax"), TOTALS),
                ),
                cross=(
                    Cross("total_2025", ("operations_2025", "players_2025"), CROSS_ROWS),
                    Cross("total_2024", ("operations_2024", "players_2024"), CROSS_ROWS),
                ),
            ),
            TableSpec(
                "staff", 34, ("2025", "2024"), STAFF_ROWS,
                select=r"^wages and salaries$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        figures=(
            FigureSpec("revenue_total", (("pnl", "group_turnover"),), "total_2025",
                       note="Incluye 454 de player trading (sobre todo cesiones), en la columna "
                            "de traspasos."),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
        ),
    ),
)
