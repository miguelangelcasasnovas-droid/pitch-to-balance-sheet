"""Especificación de extracción de cada club: páginas, filas, cuadres, moneda y unidad."""

from pitch_to_balance_sheet.extract.clubs import (
    ajax,
    arsenal,
    benfica,
    borussia_dortmund,
    celtic,
    chelsea,
    juventus,
    liverpool,
    manchester_city,
    manchester_united,
    newcastle,
    tottenham,
)

SPECS = {
    module.SPEC.club_id: module.SPEC
    for module in (arsenal, chelsea, liverpool, manchester_city, tottenham, newcastle,
                   manchester_united, juventus, borussia_dortmund, celtic, ajax, benfica)
}
