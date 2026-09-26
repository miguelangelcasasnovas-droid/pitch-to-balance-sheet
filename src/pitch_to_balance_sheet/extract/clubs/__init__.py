"""Especificación de extracción de cada club: páginas, filas, cuadres, moneda y unidad."""

from pitch_to_balance_sheet.extract.clubs import (
    arsenal,
    celtic,
    chelsea,
    juventus,
    liverpool,
    manchester_city,
    newcastle,
    tottenham,
)

SPECS = {
    module.SPEC.club_id: module.SPEC
    for module in (arsenal, chelsea, liverpool, manchester_city, tottenham, newcastle, celtic,
                   juventus)
}
