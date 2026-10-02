"""Extractores de las cuentas de referencia de las transacciones precedentes
(config/transactions.yaml): revenue_ex_player_trading, borrowings, cash y, donde hace falta,
shares_outstanding y related_party_financing. Uno por club y temporada."""

from pitch_to_balance_sheet.extract.references import (
    chelsea_2020_21,
    everton_2022_23,
    manchester_united_2022_23,
    milan_2020_21,
    newcastle_2019_20,
    roma_2018_19,
)

REFERENCE_SPECS = {
    ("chelsea", "2020/21"): chelsea_2020_21.SPEC,
    ("manchester_united", "2022/23"): manchester_united_2022_23.SPEC,
    ("milan", "2020/21"): milan_2020_21.SPEC,
    ("newcastle", "2019/20"): newcastle_2019_20.SPEC,
    ("everton", "2022/23"): everton_2022_23.SPEC,
    ("roma", "2018/19"): roma_2018_19.SPEC,
}
