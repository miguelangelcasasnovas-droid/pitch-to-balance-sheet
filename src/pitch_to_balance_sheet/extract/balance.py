"""Conceptos de balance (fase 3b): ayudas para escribir las cifras de cada club.

Cada concepto de balance (deuda financiera, arrendamientos, acreedores y deudores por traspasos)
va con su parte corriente y su parte no corriente cuando el club las separa; si no, esas dos son
hueco con su motivo. Definiciones en la sección 9 del plan.
"""

from pitch_to_balance_sheet.extract.statements import FigureSpec, Part

FRS102_LEASES = (
    "FRS 102: los arrendamientos operativos no se reconocen en el balance (solo se informan sus "
    "compromisos), así que la cifra no es comparable con la de los clubes que aplican la NIIF 16."
)


def _parts(parts) -> tuple[Part, ...]:
    return (parts,) if isinstance(parts, Part) else tuple(parts)


def split(concept: str, current, non_current, column: str, total=None, note: str = "",
          negate: bool = False, unit: str | None = None,
          expect_zero: bool = False) -> tuple[FigureSpec, ...]:
    """El concepto con su parte corriente y su parte no corriente (una celda o varias, con su
    signo). El total es la celda publicada si la hay (un cuadre de la especificación tiene que
    unirla a las dos partes) o, si no, la suma de las dos, derivada."""
    current, non_current = _parts(current), _parts(non_current)
    total = _parts(total) if total is not None else (*current, *non_current)
    return tuple(FigureSpec(name, parts, column, note=note, negate=negate, unit=unit,
                            expect_zero=expect_zero)
                 for name, parts in ((f"{concept}_current", current),
                                     (f"{concept}_non_current", non_current),
                                     (concept, total)))


def zero_from_lines(concept: str, blocks, column: str, note: str) -> tuple[FigureSpec, ...]:
    """Un concepto que el balance no tiene: 0, derivado, en cada bloque (pasivo corriente y no
    corriente), como el total del bloque menos todas sus líneas; así se comprueba que no hay
    ninguna línea más. blocks: (tabla, fila del total, filas de las líneas) del corriente y del
    no corriente, en ese orden."""
    parts = [(Part(table, total), *(Part(table, line, sign=-1) for line in lines))
             for table, total, lines in blocks]
    return split(concept, parts[0], parts[1], column, note=note, expect_zero=True)


def split_gaps(concept: str, reason: str) -> dict[str, str]:
    """Las dos partes de un concepto que el club no separa: hueco, con el motivo."""
    return {f"{concept}_current": reason, f"{concept}_non_current": reason}


def gaps(concept: str, reason: str) -> dict[str, str]:
    """Un concepto que el club no publica, con sus dos partes: hueco, con el motivo."""
    return {concept: reason, **split_gaps(concept, reason)}
