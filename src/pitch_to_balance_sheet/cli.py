"""Línea de comandos: python -m pitch_to_balance_sheet <comando>.

- download: cuentas de Companies House de una temporada, a data/raw/companies_house/.
- text-layer: capa de texto de esos PDFs, a data/processed/text_layer_<temporada>.csv.

Si un paso falla, sale con código 1 y dice por qué.
"""

import argparse
import csv
import logging
import os
import statistics
import sys
from dataclasses import asdict, fields
from datetime import UTC, datetime

from dotenv import load_dotenv

from pitch_to_balance_sheet import manifest
from pitch_to_balance_sheet.config import (
    INTERIM_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    ROOT,
    fiscal_year_end_date,
    load_clubs,
    season_slug,
)
from pitch_to_balance_sheet.extract import chelsea
from pitch_to_balance_sheet.extract import ocr as ocr_lib
from pitch_to_balance_sheet.extract.text_layer import KEYWORDS, measure
from pitch_to_balance_sheet.sources.companies_house import (
    AccountsDocument,
    CompaniesHouseClient,
    CompaniesHouseError,
    download_accounts,
)
from pitch_to_balance_sheet.sources.config import Source, load_sources

log = logging.getLogger(__name__)

MANIFEST = RAW_DIR / "manifest.csv"
SOURCE_NAMES = {"companies_house": "Companies House", "manual": "manual", "url": "web del club"}


def filings_path(season: str):
    return PROCESSED_DIR / f"companies_house_filings_{season_slug(season)}.csv"


def download(season: str) -> int:
    load_dotenv(ROOT / ".env")
    try:
        client = CompaniesHouseClient(os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip())
    except CompaniesHouseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    documents = []
    for club in load_clubs():
        made_up_date = fiscal_year_end_date(season, club.fiscal_year_end)
        log.info("%s (%s): cuentas cerradas a %s", club.name, club.companies_house_number,
                 made_up_date)
        try:
            document, entries = download_accounts(client, club, made_up_date, RAW_DIR)
        except CompaniesHouseError as exc:
            print(f"error: {club.name} ({club.companies_house_number}): {exc}", file=sys.stderr)
            return 1
        manifest.upsert(MANIFEST, entries)
        for entry in entries:
            log.info("  %s  %d bytes  sha256 %s", entry.file, entry.bytes, entry.sha256)
        documents.append(document)

    path = filings_path(season)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=[field.name for field in fields(AccountsDocument)], lineterminator="\n"
        )
        writer.writeheader()
        for document in documents:
            row = asdict(document)
            row["formats"] = " + ".join(document.formats)
            row["files"] = " + ".join(document.files)
            writer.writerow(row)
    log.info("Presentaciones en %s", path.relative_to(ROOT))
    return 0


def _pages_summary(pages: tuple[int, ...]) -> str:
    shown = ", ".join(str(page) for page in pages[:3])
    return f"p. {shown}{', …' if len(pages) > 3 else ''}"


def local_pdf(season: str, club_id: str, source: Source) -> str | None:
    """PDF local de una fuente, comprobado contra el manifiesto. None si es una URL sin bajar.

    Sale ManifestError si falta el archivo, no está registrado o su sha256 ha cambiado.
    """
    if source.kind == "url":
        return None
    if source.kind == "manual":
        try:
            manifest.verify(RAW_DIR, source.file, MANIFEST)
        except manifest.ManifestError as exc:
            raise manifest.ManifestError(
                f"{exc}. Descárgalo a mano de {source.url} y regístralo con: "
                "python -m pitch_to_balance_sheet register-manual"
            ) from exc
        return source.file
    path = filings_path(season)
    filings = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            filings = {row["club_id"]: row for row in csv.DictReader(f)}
    files = filings.get(club_id, {}).get("files", "").split(" + ")
    pdf = next((file for file in files if file.endswith(".pdf")), None)
    if pdf is None:
        raise manifest.ManifestError(
            f"falta el PDF de Companies House {season} de {club_id}. "
            "Ejecuta antes: python -m pitch_to_balance_sheet download"
        )
    manifest.verify(RAW_DIR, pdf, MANIFEST)
    return pdf


def register_manual(season: str) -> int:
    """Registra en el manifiesto los PDFs manuales de config/sources.yaml."""
    registered = manifest.read(MANIFEST)
    for club_id, club_sources in load_sources(season).items():
        for source in club_sources.all:
            if source.kind != "manual":
                continue
            path = RAW_DIR / source.file
            if not path.exists():
                print(f"error: {club_id}: falta data/raw/{source.file}. "
                      f"Descárgalo a mano de {source.url}", file=sys.stderr)
                return 1
            if not path.read_bytes()[:5] == b"%PDF-":
                print(f"error: {club_id}: data/raw/{source.file} no es un PDF", file=sys.stderr)
                return 1
            sha256 = manifest.sha256_file(path)
            previous = registered.get(source.file)
            if previous and previous["sha256"] != sha256:
                print(f"error: {club_id}: data/raw/{source.file} ha cambiado desde que se "
                      f"registró (sha256 {previous['sha256']} y ahora {sha256}). Si es a "
                      "propósito, quita su fila del manifiesto y vuelve a registrarlo",
                      file=sys.stderr)
                return 1
            if previous:
                log.info("%s: data/raw/%s ya estaba registrado", club_id, source.file)
                continue
            # La fecha de descarga de un archivo manual es la de su última modificación.
            modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            entry = manifest.ManifestEntry(
                file=source.file,
                url=source.url,
                retrieved_at=modified.isoformat(timespec="seconds"),
                sha256=sha256,
                bytes=path.stat().st_size,
                content_type="application/pdf",
            )
            manifest.upsert(MANIFEST, [entry])
            log.info("%s: registrado data/raw/%s  %d bytes  sha256 %s  %s", club_id,
                     entry.file, entry.bytes, entry.sha256, entry.retrieved_at)
    return 0


def text_layer(season: str) -> int:
    names = {club.club_id: club.name for club in load_clubs()}
    rows, summary, per_page, errors, not_downloaded = [], [], [], [], []
    for club_id, club_sources in load_sources(season).items():
        for source in club_sources.all:
            label = f"{names.get(club_id, club_id)} · {SOURCE_NAMES[source.kind]}"
            try:
                pdf = local_pdf(season, club_id, source)
            except manifest.ManifestError as exc:
                errors.append(f"{label}: {exc}")
                continue
            if pdf is None:
                not_downloaded.append(label)
                continue
            try:
                layer = measure(RAW_DIR / pdf)
            except Exception as exc:
                # Ni pdfplumber ni pypdfium2 lo abren: se miden los demás y se acaba con error.
                errors.append(f"{label}: no se puede leer {pdf}: {exc!r}")
                continue
            for number, chars in enumerate(layer.chars_per_page, start=1):
                rows.append({
                    "club_id": club_id,
                    "source": source.kind,
                    "file": pdf,
                    "engine": layer.engine,
                    "page": number,
                    "chars": chars,
                    **{term.replace(" ", "_"): number in layer.keyword_pages[term]
                       for terms in KEYWORDS.values() for term in terms},
                })
            chars = layer.chars_per_page
            keywords = [
                f"{term.capitalize()} ({_pages_summary(layer.keyword_pages[term])})"
                for group in KEYWORDS for term in layer.keywords_found(group)
            ]
            summary.append((label, layer.engine, layer.pages, layer.text_pages,
                            f"{min(chars)} · {statistics.median(chars):g} · {max(chars)}",
                            ", ".join(keywords) or "ninguna", layer.classification))
            per_page.append(f"{label}: {' '.join(str(c) for c in chars)}")

    out = PROCESSED_DIR / f"text_layer_{season_slug(season)}.csv"
    if rows:
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    print("| Club · fuente | Motor | Páginas | Págs. con texto | Caracteres por página "
          "(mín · mediana · máx) | Palabras clave | Clasificación |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in summary:
        print("| " + " | ".join(str(value) for value in row) + " |")
    print("\nCaracteres por página:")
    print("\n".join(per_page))
    if not_downloaded:
        print(f"\nSin medir, URL todavía sin descargar: {', '.join(not_downloaded)}")
    if rows:
        print(f"Detalle por página en {out.relative_to(ROOT)}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def ocr(season: str, club_id: str) -> int:
    """OCR de las páginas localizadas (pages en config/sources.yaml) de la fuente principal."""
    club_sources = load_sources(season).get(club_id)
    if club_sources is None or not club_sources.primary.pages:
        print(f"error: {club_id}: no hay páginas localizadas para {season} en "
              "config/sources.yaml", file=sys.stderr)
        return 1
    try:
        pdf = local_pdf(season, club_id, club_sources.primary)
        if pdf is None:
            raise manifest.ManifestError("la fuente principal es una URL todavía sin descargar")
        sha256 = manifest.read(MANIFEST)[pdf]["sha256"]
        for name, page in club_sources.primary.pages.items():
            paths = ocr_lib.ocr_page(RAW_DIR / pdf, sha256, page, INTERIM_DIR / "ocr")
            log.info("%s: pág. %d (%s) -> %s", club_id, page, name,
                     paths["json"].relative_to(ROOT))
    except (manifest.ManifestError, ocr_lib.OcrError) as exc:
        print(f"error: {club_id}: {exc}", file=sys.stderr)
        return 1
    return 0


EXTRACTORS = {"chelsea": chelsea}


def extract(season: str, club_id: str) -> int:
    """Piloto: tres cifras de las páginas ya pasadas por OCR, cuadres y recortes."""
    module = EXTRACTORS.get(club_id)
    club = next((c for c in load_clubs() if c.club_id == club_id), None)
    if module is None or club is None:
        print(f"error: no hay extractor para {club_id}", file=sys.stderr)
        return 1
    source = load_sources(season)[club_id].primary
    try:
        pdf = local_pdf(season, club_id, source)
        sha256 = manifest.read(MANIFEST)[pdf]["sha256"]
        figures, checks, pages = module.extract(INTERIM_DIR / "ocr" / sha256)
    except (manifest.ManifestError, ocr_lib.OcrError, chelsea.ExtractionError) as exc:
        print(f"error: {club_id}: {exc}", file=sys.stderr)
        return 1

    slug = f"{club_id}_{season_slug(season)}"
    images = {page.page: page.image_path for page in pages}
    rows = []
    print("Cifras:")
    for figure in figures:
        crop_path = INTERIM_DIR / "recortes" / f"{slug}_{figure.concept}_p{figure.page}.png"
        crop = ocr_lib.crop_row(images[figure.page], figure.row, crop_path)
        amount = figure.amount
        rows.append({
            "club_id": club_id,
            "season": season,
            "fiscal_year_end": fiscal_year_end_date(season, club.fiscal_year_end).isoformat(),
            "concept": figure.concept,
            "label_original": figure.label_original,
            "column": figure.column,
            "value_reported": amount.value,
            "unit_reported": module.UNIT,
            "currency_reported": module.CURRENCY,
            "value_full": amount.value * module.MULTIPLIER,
            "source_file": pdf,
            "source_page": figure.page,
            "sha256": sha256,
            "extraction_method": ocr_lib.ENGINE,
            "ocr_raw": amount.raw,
            "ocr_confidence": amount.confidence,
            "ocr_fixes": "; ".join(amount.fixes),
            "crop": str(crop.relative_to(ROOT)),
        })
        print(f"  {figure.concept}: {amount.value:,} miles de {module.CURRENCY} "
              f"(pág. {figure.page}, {figure.label_original!r}, columna {figure.column}, "
              f"OCR {amount.raw!r}) -> {crop.relative_to(ROOT)}")

    print("\nCuadres (tolerancia de redondeo ±1):")
    for check in checks:
        print(f"  {'OK   ' if check.ok else 'FALLA'} pág. {check.page} [{check.column}] "
              f"{check.relation}: {check.reported:,} frente a {check.computed:,} "
              f"(diferencia {check.difference:,})")

    print("\nCorrecciones sobre lo que leyó el OCR en las tablas usadas:")
    for page in pages:
        units = [unit for table in page.tables for unit in table.unit_raw]
        misread = [unit for unit in units if not unit.startswith("£")]
        print(f"  pág. {page.page}: cabeceras de unidad {units}"
              + (f" -> {len(misread)} leídas sin £" if misread else ""))
        for table in page.tables:
            for table_row in table.rows:
                for column, amount in table_row.amounts.items():
                    if amount.fixes:
                        print(f"  pág. {page.page} {table_row.raw_label or '(total)'!r} "
                              f"col. {column}: {amount.raw!r} -> {amount.value:,} "
                              f"({'; '.join(amount.fixes)})")

    for name, data in (("cifras", rows), ("cuadres", [
        {"page": c.page, "relation": c.relation, "column": c.column, "reported": c.reported,
         "computed": c.computed, "difference": c.difference, "ok": c.ok} for c in checks
    ])):
        out = INTERIM_DIR / f"piloto_{slug}_{name}.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
        print(f"\n{name.capitalize()} en {out.relative_to(ROOT)}", end="")
    print()
    failed = [c for c in checks if not c.ok]
    if failed:
        print(f"error: {len(failed)} cuadres no cuadran", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pitch_to_balance_sheet")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("download", "descarga las cuentas de Companies House de una temporada"),
        ("register-manual", "registra en el manifiesto los PDFs descargados a mano"),
        ("text-layer", "mide la capa de texto de los PDFs locales de config/sources.yaml"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--season", default="2024/25", help="temporada, p. ej. 2024/25")
    for name, help_text in (
        ("ocr", "OCR de las páginas localizadas de un club"),
        ("extract", "piloto: tres cifras, cuadres y recortes de un club ya pasado por OCR"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--season", default="2024/25", help="temporada, p. ej. 2024/25")
        command.add_argument("--club", required=True, help="club_id, p. ej. chelsea")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        fiscal_year_end_date(args.season, "06-30")
        load_sources(args.season)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.command == "ocr":
        return ocr(args.season, args.club)
    if args.command == "extract":
        return extract(args.season, args.club)
    commands_by_name = {
        "download": download,
        "register-manual": register_manual,
        "text-layer": text_layer,
    }
    return commands_by_name[args.command](args.season)
