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
Fase 3a:
- pág. 33, nota 2, Revenue and other income: las partidas de ingresos (mapeo en
  config/line_items.yaml).
- pág. 38, nota 10, Intangible fixed assets de 2025: el bloque "Amortisation and impairment",
  columna Player registrations. No tiene línea de deterioro en 2025; la pág. 39 lo dice en una
  frase: "impaired by £nil (2024: £1,770,000)".
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
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

REVENUE_ROWS = {
    "match_receipts": r"^match receipts$",
    "uefa": r"^uefa prize money$",
    "tv_media": r"^tv and media$",
    "commercial": r"^commercial$",
    "revenue": r"^revenue$",
}
INTANGIBLE_ROWS = {
    "opening": r"^at 30 june 2024$",
    "charge": r"^charged in year - amortisation$",
    "disposals": r"^disposals$",
    "closing": r"^at 30 june 2025$",
}
MIX = mix.for_club("tottenham")
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
            TableSpec(
                "revenue", 33, ("2025", "2024"), REVENUE_ROWS, header=r"^20(24|25)$",
                select=REVENUE_ROWS["match_receipts"],
                sums=(Sum("revenue", tuple(REVENUE_ROWS)[:-1]),),
            ),
            TableSpec(
                "intangibles", 38, ("players", "software", "total"), INTANGIBLE_ROWS,
                select=INTANGIBLE_ROWS["charge"],
                block=(r"^amortisation and impairment$", INTANGIBLE_ROWS["closing"]),
                sums=(Sum("closing", ("opening", "charge", "disposals"), ("players", "total")),
                      Sum("closing", ("opening", "charge"), ("software",))),
                cross=(Cross("total", ("players", "software"), ("opening", "charge", "closing")),),
            ),
        ),
        links=(
            Link(("revenue", "revenue", "2025"), ("pnl", "revenue", "total_2025")),
            Link(("revenue", "revenue", "2024"), ("pnl", "revenue", "total_2024")),
            MIX.check(),
        ),
        gaps=MIX.gaps(),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025"),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "charge", "players"),), "2025",
                       note="Charged in year - amortisation de Player registrations (nota 10)."),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_intangibles"),),
                       "total_2025",
                       note="Profit on disposal of intangible fixed assets: en 2025 solo hay "
                            "bajas de derechos de jugadores; el software no tiene (nota 10)."),
        ),
        sentences=(
            SentenceFigureSpec(
                "impairment_player_registrations", 39, "impaired by £nil",
                # El OCR lee la £ como otra letra ("Enil").
                r"were impaired by \S?(?P<amount>nil) \(2024", "2025", scale=1000,
                note="Nota 10 (pág. 39): «capitalised player registrations relating to zero "
                     "individuals (2024: one) were impaired by £nil»: el deterioro de 2025 es "
                     "cero, publicado en el texto."),
            SentenceFigureSpec(
                "staff_severance_disclosed", 35, "redundancy costs",
                # La cifra del año anterior ancla la frase; el OCR no lee el paréntesis ni la £.
                r"redundancy costs of (?P<amount>\S+) \(?2024: ?£?86,000\)", "2025",
                scale=1000, image_reading="£153,000", note=SEVERANCE_NOTE,
                included_in_staff_costs="false"),
        ),
    ),
)
