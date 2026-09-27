"""Tottenham Hotspur Limited, cuentas 2024/25 de Companies House: escaneo, OCR.

pdfplumber no puede abrir este PDF; pypdfium2 lo renderiza. Páginas localizadas a mano mirando
la página renderizada:
- pág. 23, Consolidated income statement: seis columnas en £'000 (operaciones sin football
  trading, football trading y total, de 2025 y de 2024). De "Finance income" hacia abajo solo
  hay cifras en las columnas de total: esas filas se cuadran solo ahí.
- pág. 35, nota 5, Staff numbers and costs (continued), 2025 y 2024 en £'000. Debajo, en una
  frase, las indemnizaciones por despido, en libras y fuera del total de personal
  (staff_severance_disclosed, informativa). El OCR lee mal esa cifra ("€153,00"); en la imagen
  se lee "£153,000".
"""

from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    SentenceFigureSpec,
    Sum,
    TableSpec,
)
from pitch_to_balance_sheet.extract.tables import THOUSANDS_EVIDENCE

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025",
               "operations_2024", "players_2024", "total_2024")
TOTALS = ("total_2025", "total_2024")
PNL_ROWS = {
    "revenue": r"^revenue$",
    "other_income": r"^other income$",
    "operating_expenses": r"^operating expenses$",
    "operating_result": r"^operating profit/\(loss\)$",
    # Rótulo en dos líneas; las cifras van en la segunda.
    "profit_disposal_intangibles": r"^profit on disposal of intangible fixed assets$",
    # El OCR lee "Profit/loss) from operations": el paréntesis de apertura es opcional.
    "result_from_operations": r"^profit/\(?loss\) from operations$",
    "finance_income": r"^finance income$",
    "finance_costs": r"^finance costs$",
    "result_before_tax": r"^loss before taxation$",
    "tax": r"^tax$",
    "net_result": r"^loss for the year$",
}
CROSS_ROWS = tuple(PNL_ROWS)[:6]
STAFF_ROWS = {
    "salaries_and_bonuses": r"^salaries and bonuses$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs",
}

SEVERANCE_NOTE = (
    "Nota 5 (pág. 35): «In addition to the above payroll costs, redundancy costs of £153,000 "
    "(2024: £86,000) were also charged to the income statement during the year.» Fuera del "
    "total de personal y sin clasificar como excepcional. En libras en la frase: 153 miles. "
    "Informativa: no ajusta ninguna métrica."
)
REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 23) separa la columna de football trading, y en Revenue "
    "esa columna es un guion: no hay traspasos ni cesiones."
)

SPEC = ClubSpec(
    club_id="tottenham",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £'000 de las págs. 23 y 35, vistas en la página renderizada. La "
               "moneda no se toma del OCR.",
    primary=DocumentSpec(
        method="ocr",
        unit_evidence=THOUSANDS_EVIDENCE,
        tables=(
            TableSpec(
                "pnl", 23, PNL_COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_result", ("revenue", "other_income", "operating_expenses")),
                    Sum("result_from_operations", ("operating_result",
                                                   "profit_disposal_intangibles")),
                    Sum("result_before_tax", ("result_from_operations", "finance_income",
                                              "finance_costs"), TOTALS),
                    Sum("net_result", ("result_before_tax", "tax"), TOTALS),
                ),
                cross=(
                    Cross("total_2025", ("operations_2025", "players_2025"), CROSS_ROWS),
                    Cross("total_2024", ("operations_2024", "players_2024"), CROSS_ROWS),
                ),
            ),
            TableSpec(
                "staff", 35, ("2025", "2024"), STAFF_ROWS,
                # El OCR solo lee una de las dos cabeceras £'000; la fila de años, entera.
                header=r"^20(24|25)$",
                select=r"^salaries and bonuses$",
                totals_after={"staff_costs_total": "other_pension_costs"},
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)),),
            ),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
        ),
        sentences=(
            SentenceFigureSpec(
                "staff_severance_disclosed", 35, "redundancy costs",
                # La cifra del año anterior ancla la frase; el OCR no lee el paréntesis ni la £.
                r"redundancy costs of (?P<amount>\S+) \(?2024: ?£?86,000\)", "2025",
                scale=1000, image_reading="£153,000", note=SEVERANCE_NOTE,
                included_in_staff_costs="false"),
        ),
    ),
)
