"""Manchester City Football Club Limited, 2024/25: PDF digital del club, descargado a mano.

Texto directo con pdfplumber, sin OCR. Páginas localizadas buscando los títulos en el texto:
- pág. 20, Statement of Profit or Loss: cuatro columnas en £000 (operaciones sin traspasos 2025,
  traspasos y amortización 2025, total 2025 y total 2024).
- pág. 37, nota 7, Employees: "aggregate payroll costs", 2025 y 2024 en £000. El total incluye
  los pagos basados en acciones.
- pág. 35, nota 4, Revenue: las partidas de ingresos (mapeo en config/line_items.yaml).
- pág. 42, nota 12, Intangible fixed assets: el cargo del año de los derechos de jugadores. La
  nota no separa amortización y deterioro: la nota 5 (pág. 36) lo llama "Amortisation and
  impairment of intangible assets".
"""

from pitch_to_balance_sheet.extract import mix
from pitch_to_balance_sheet.extract.statements import (
    ClubSpec,
    Cross,
    DocumentSpec,
    FigureSpec,
    Link,
    Sum,
    TableSpec,
)

PNL_COLUMNS = ("operations_2025", "players_2025", "total_2025", "total_2024")
PNL_ROWS = {
    "revenue": r"^revenue$",
    "other_operating_income": r"^other operating income$",
    "operating_expenses": r"^operating expenses$",
    "operating_loss": r"^operating loss$",
    "profit_disposal_players": r"^profit on disposal of players registrations$",
    "result_before_interest": r"^profit before interest and taxation$",
    "interest_receivable": r"^interest receivable and similar income$",
    "interest_payable": r"^interest payable and similar charges$",
    "result_before_tax": r"^\(loss\)/profit on ordinary activities before taxation$",
    "tax": r"^taxation$",
    "net_result": r"^\(loss\)/profit on ordinary activities after taxation$",
}
STAFF_ROWS = {
    "wages_and_salaries": r"^wages and salaries$",
    "social_security_costs": r"^social security costs$",
    "other_pension_costs": r"^other pension costs$",
    "share_based_payments": r"^share-based payments$",
    "staff_costs_total": r"^total$",
}

REVENUE_ROWS = {
    "matchday": r"^matchday$",
    "broadcasting_uefa": r"^broadcasting - uefa$",
    "broadcasting_other": r"^broadcasting - all other$",
    "other_commercial": r"^other commercial activities$",
    "total": r"^total$",
}
INTANGIBLE_ROWS = {"charge": r"^charge in the year$"}
MIX = mix.for_club("manchester_city")
AMORTISATION_NOTE = (
    "Charge in the year de Players' registrations (nota 12). Incluye el deterioro, si lo hay: la "
    "nota 5 (pág. 36) lo llama «Amortisation and impairment» y la nota 12 no lo separa."
)
REVENUE_EX_NOTE = (
    "La cuenta de resultados (pág. 20) separa la columna de traspasos y amortización, y en "
    "Revenue esa columna es un guion: no hay traspasos ni cesiones."
)

PLAYER_OTHER_INCOME_GAP = (
    "no se publica por separado: la cuenta y las notas leídas no dan ingresos por cesiones, "
    "sell-on ni bonus fuera de profit_on_player_disposals"
)


SPEC = ClubSpec(
    club_id="manchester_city",
    currency="GBP",
    unit="thousands",
    multiplier=1000,
    unit_basis="Cabeceras £000 de las págs. 20 y 37, en el texto del PDF.",
    primary=DocumentSpec(
        method="text",
        unit_evidence=r"£000",
        tables=(
            TableSpec(
                "pnl", 20, PNL_COLUMNS, PNL_ROWS,
                sums=(
                    Sum("operating_loss", ("revenue", "other_operating_income",
                                           "operating_expenses")),
                    Sum("result_before_interest", ("operating_loss", "profit_disposal_players")),
                    Sum("result_before_tax", ("result_before_interest", "interest_receivable",
                                              "interest_payable")),
                    Sum("net_result", ("result_before_tax", "tax")),
                ),
                cross=(Cross("total_2025", ("operations_2025", "players_2025"),
                             tuple(PNL_ROWS)),),
            ),
            TableSpec(
                "staff", 37, ("2025", "2024"), STAFF_ROWS,
                sums=(Sum("staff_costs_total", tuple(STAFF_ROWS)[:-1]),),
            ),
            TableSpec(
                "revenue", 35, ("2025", "2024"), REVENUE_ROWS,
                sums=(Sum("total", tuple(REVENUE_ROWS)[:-1]),),
            ),
            TableSpec(
                "intangibles", 42, ("other", "players", "total"), INTANGIBLE_ROWS,
                cross=(Cross("total", ("other", "players"), ("charge",)),),
            ),
        ),
        links=(
            Link(("revenue", "total", "2025"), ("pnl", "revenue", "total_2025")),
            Link(("revenue", "total", "2024"), ("pnl", "revenue", "total_2024")),
            # El cargo de la nota 12 es la columna de traspasos y amortización de la cuenta.
            Link(("intangibles", "charge", "total"), ("pnl", "operating_expenses", "players_2025"),
                 sign=-1),
            MIX.check(),
        ),
        figures=(
            FigureSpec("revenue_total_reported", (("pnl", "revenue"),), "total_2025"),
            FigureSpec("revenue_ex_player_trading", (("pnl", "revenue"),), "total_2025",
                       note=REVENUE_EX_NOTE),
            FigureSpec("staff_costs", (("staff", "staff_costs_total"),), "2025",
                       note="Incluye 531 de pagos basados en acciones."),
            FigureSpec("net_result", (("pnl", "net_result"),), "total_2025"),
            *MIX.figures("2025"),
            FigureSpec("amortisation_player_registrations",
                       (("intangibles", "charge", "players"),), "2025", note=AMORTISATION_NOTE),
            FigureSpec("profit_on_player_disposals", (("pnl", "profit_disposal_players"),),
                       "total_2025", note="Profit on disposal of players' registrations."),
        ),
        gaps={
            **MIX.gaps(),
            "player_trading_other_income": PLAYER_OTHER_INCOME_GAP,
            "impairment_player_registrations": (
                "no se publica por separado: la nota 12 (pág. 42) da un solo cargo del año, "
                "169,546, que la nota 5 (pág. 36) llama «Amortisation and impairment of "
                "intangible assets»; va entero en amortisation_player_registrations"),
        },
    ),
)
