"""Extracción de las cifras de cada club: fuente principal, controles, recortes y tablas.

Un club que falla (falta un archivo, una fila o una celda, un cuadre no cuadra o el control no
coincide) queda en error con el motivo, y se sigue con el siguiente.
"""

import csv
from dataclasses import dataclass, field

from PIL import Image

from pitch_to_balance_sheet import manifest
from pitch_to_balance_sheet.config import (
    INTERIM_DIR,
    RAW_DIR,
    ROOT,
    fiscal_year_end_date,
    load_clubs,
    season_slug,
)
from pitch_to_balance_sheet.extract import ocr
from pitch_to_balance_sheet.extract.statements import (
    Check,
    ClubSpec,
    ExtractionError,
    Figure,
    read_document,
)
from pitch_to_balance_sheet.sources.local import document_file

SOURCE_NAMES = {"companies_house": "Companies House", "manual": "PDF manual", "url": "web del club"}
CONCEPTS = ("revenue_total_reported", "revenue_ex_player_trading", "staff_costs",
            "staff_costs_exceptional", "net_result")
RESTATEMENT_THRESHOLD_PCT = 1.0  # sección 5 del plan


@dataclass(frozen=True)
class Restatement:
    """Una cifra frente a la del informe del año siguiente (control de reexpresión)."""

    document: str
    concept: str
    page: int
    primary: int
    control: int

    @property
    def difference(self) -> int:
        return self.control - self.primary

    @property
    def pct(self) -> float:
        if self.primary == 0:
            return 0.0 if self.control == 0 else float("inf")
        return abs(self.difference) / abs(self.primary) * 100

    @property
    def restated(self) -> bool:
        return self.pct > RESTATEMENT_THRESHOLD_PCT


@dataclass
class ClubResult:
    club_id: str
    spec: ClubSpec
    source: str = ""
    pdf: str = ""
    sha256: str = ""
    figures: list[Figure] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    crops: dict[str, str] = field(default_factory=dict)
    restatements: list[Restatement] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)  # resumen de cada control, para la tabla
    error: str | None = None

    @property
    def failed(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]


def crop_figure(figure: Figure, path) -> None:
    """Recorte de cada fila que entra en la cifra (sin repetir), apiladas si son varias."""
    crops, seen = [], set()
    for component in figure.components:
        key = (component.image_path, id(component.row))
        if key in seen:
            continue
        seen.add(key)
        x1, y1, x2, y2 = component.row.box
        with Image.open(component.image_path) as image:
            crops.append(image.crop((max(int(x1) - 4, 0), max(int(y1) - 4, 0),
                                     min(int(x2) + 4, image.width),
                                     min(int(y2) + 4, image.height))).convert("L"))
    gap = 12
    result = Image.new("L", (max(c.width for c in crops),
                             sum(c.height for c in crops) + gap * (len(crops) - 1)), 255)
    y = 0
    for crop in crops:
        result.paste(crop, (0, y))
        y += crop.height + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    result.save(path)


def extract_club(season: str, spec: ClubSpec, reocr: bool = False) -> ClubResult:
    result = ClubResult(spec.club_id, spec)
    try:
        source, pdf, sha256 = document_file(season, spec.club_id, None)
        result.source, result.pdf, result.sha256 = SOURCE_NAMES[source.kind], pdf, sha256
        primary = read_document("principal", spec.primary, RAW_DIR / pdf, sha256, INTERIM_DIR,
                                reocr)
        result.figures = primary.figures
        result.checks = list(primary.checks)
        result.corrections = list(primary.corrections)
        result.summary = dict(primary.summary)
        for control in spec.controls:
            control_source, control_pdf, control_sha = document_file(
                season, spec.club_id, control.control_index)
            name = f"control: {SOURCE_NAMES[control_source.kind]}"
            other = read_document(name, control, RAW_DIR / control_pdf, control_sha,
                                  INTERIM_DIR, reocr)
            result.checks += other.checks
            result.corrections += [f"{name}: {note}" for note in other.corrections]
            twins = {figure.concept: figure for figure in other.figures}
            for figure in primary.figures:
                twin = twins.get(figure.concept)
                if twin is None:
                    raise ExtractionError(f"el {name} no tiene {figure.concept}")
                if control.control_kind == "restatement":
                    result.restatements.append(Restatement(name, figure.concept, twin.page,
                                                           figure.value, twin.value))
                else:
                    result.checks.append(Check(
                        name, twin.page, f"{figure.concept}: principal = control",
                        figure.column, figure.value, twin.value))
            if control.control_kind == "restatement":
                marked = [r for r in result.restatements if r.document == name and r.restated]
                result.controls.append(
                    f"{name}: reexpresión en " + ", ".join(
                        f"{r.concept} ({r.pct:.1f}%)" for r in marked)
                    if marked else f"{name}: sin reexpresión (>{RESTATEMENT_THRESHOLD_PCT:g}%)")
            else:
                result.controls.append(f"{name}: cifras idénticas")
    except (manifest.ManifestError, ExtractionError, ocr.OcrError) as exc:
        result.error = str(exc)
        return result
    slug = f"{spec.club_id}_{season_slug(season)}"
    for figure in result.figures:
        path = INTERIM_DIR / "recortes" / f"{slug}_{figure.concept}_p{figure.page}.png"
        crop_figure(figure, path)
        result.crops[figure.concept] = str(path.relative_to(ROOT))
    if result.failed:
        result.error = f"{len(result.failed)} de {len(result.checks)} cuadres no cuadran"
    return result


def write_outputs(season: str, results: list[ClubResult]) -> list[str]:
    fiscal_year_ends = {club.club_id: club.fiscal_year_end for club in load_clubs()}
    figures, checks = [], []
    for result in results:
        spec = result.spec
        for figure in result.figures:
            figures.append({
                "club_id": result.club_id,
                "season": season,
                "fiscal_year_end": fiscal_year_end_date(
                    season, fiscal_year_ends[result.club_id]).isoformat(),
                "concept": figure.concept,
                "value_reported": figure.value,
                "unit_reported": spec.unit,
                "currency_reported": spec.currency,
                "value_full": figure.value * spec.multiplier,
                "is_derived": figure.is_derived,
                "components": figure.sources,
                "source": result.source,
                "source_file": result.pdf,
                "source_page": figure.page,
                "label_original": figure.label,
                "column": figure.column,
                "sha256": result.sha256,
                "extraction_method": (ocr.ENGINE if figure.method == "ocr"
                                      else "pdfplumber (texto del PDF)"),
                "ocr_note": figure.ocr_note,
                "ocr_raw": " ; ".join(a.raw for a in figure.amounts),
                "definition_note": figure.note,
                "crop": result.crops.get(figure.concept, ""),
                "status": "error" if result.error else "ok",
            })
        for check in result.checks:
            checks.append({"club_id": result.club_id, "document": check.document,
                           "page": check.page, "relation": check.relation,
                           "column": check.column, "reported": check.reported,
                           "computed": check.computed, "difference": check.difference,
                           "ok": check.ok})
    restatements = [
        {"club_id": result.club_id, "document": r.document, "concept": r.concept,
         "page": r.page, "primary": r.primary, "control": r.control,
         "difference": r.difference, "pct": round(r.pct, 3), "restated": r.restated}
        for result in results for r in result.restatements
    ]
    written = []
    done = {result.club_id for result in results}
    for name, rows in (("cifras", figures), ("cuadres", checks),
                       ("reexpresiones", restatements)):
        path = INTERIM_DIR / f"{name}_{season_slug(season)}.csv"
        # Las filas de los clubes que no se han vuelto a extraer se conservan.
        if path.exists():
            with path.open(newline="", encoding="utf-8") as f:
                rows = [row for row in csv.DictReader(f) if row["club_id"] not in done] + rows
        if not rows:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[-1]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        written.append(str(path.relative_to(ROOT)))
    return written


def summary_note(result: ClubResult) -> str:
    if not result.summary:
        return "sin correcciones"
    return "; ".join(f"{count} {name}" for name, count in result.summary.items())


def _value(figure: Figure | None) -> str:
    if figure is None:
        return "—"
    text = f"{figure.value:,}" if figure.value >= 0 else f"({-figure.value:,})"
    return text + (" *" if figure.is_derived else "")


def table(results: list[ClubResult]) -> str:
    """Tabla final. Un * marca las cifras derivadas (is_derived)."""
    names = {club.club_id: club.name for club in load_clubs()}
    lines = ["| Club | Fuente | Ingresos publicados | Ingresos sin traspasos | "
             "Gastos de personal | Personal excepcional | Resultado neto | Moneda | Unidad | "
             "Páginas | Cuadres | Controles | Notas de OCR |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for result in results:
        by_concept = {figure.concept: figure for figure in result.figures}
        ok = not result.error
        values = [_value(by_concept.get(c)) if ok else "—" for c in CONCEPTS]
        pages = " · ".join(
            "+".join(dict.fromkeys(str(comp.page) for comp in by_concept[c].components))
            for c in CONCEPTS if c in by_concept
        ) or "—"
        passed = sum(check.ok for check in result.checks)
        checks = (f"OK ({passed}/{len(result.checks)})" if ok
                  else f"FALLA ({passed}/{len(result.checks)})" if result.checks else "ERROR")
        lines.append(f"| {names.get(result.club_id, result.club_id)} | {result.source or '—'} | "
                     + " | ".join(values)
                     + f" | {result.spec.currency} | {result.spec.unit} | {pages} | {checks} | "
                     f"{'; '.join(result.controls) or '—'} | "
                     f"{summary_note(result) if ok else 'error: ' + result.error} |")
    return "\n".join(lines)
