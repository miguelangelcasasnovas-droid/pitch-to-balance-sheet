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

from dotenv import load_dotenv

from pitch_to_balance_sheet import manifest
from pitch_to_balance_sheet.config import (
    PROCESSED_DIR,
    RAW_DIR,
    ROOT,
    fiscal_year_end_date,
    load_clubs,
    season_slug,
)
from pitch_to_balance_sheet.extract.text_layer import KEYWORDS, measure
from pitch_to_balance_sheet.sources.companies_house import (
    AccountsDocument,
    CompaniesHouseClient,
    CompaniesHouseError,
    download_accounts,
)

log = logging.getLogger(__name__)

FORMAT_NAMES = {"application/pdf": "PDF", "application/xhtml+xml": "XHTML"}


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
        manifest.upsert(RAW_DIR / "manifest.csv", entries)
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


def text_layer(season: str) -> int:
    path = filings_path(season)
    if not path.exists():
        print(f"error: falta {path.relative_to(ROOT)}. Ejecuta antes: "
              "python -m pitch_to_balance_sheet download", file=sys.stderr)
        return 1
    with path.open(newline="", encoding="utf-8") as f:
        filings = {row["club_id"]: row for row in csv.DictReader(f)}

    rows, summary, per_page, errors = [], [], [], []
    for club in load_clubs():
        filing = filings.get(club.club_id)
        pdf = next((f for f in (filing or {}).get("files", "").split(" + ") if f.endswith(".pdf")),
                   None)
        if filing is None or pdf is None or not (RAW_DIR / pdf).exists():
            print(f"error: {club.name}: falta el PDF de cuentas {season} en data/raw/. "
                  "Ejecuta antes: python -m pitch_to_balance_sheet download", file=sys.stderr)
            return 1
        formats = " + ".join(FORMAT_NAMES.get(ct, ct) for ct in filing["formats"].split(" + "))
        try:
            layer = measure(RAW_DIR / pdf)
        except Exception as exc:
            # PDF ilegible: se miden los demás y el comando acaba con error, con el motivo.
            errors.append(f"{club.name}: pdfplumber no puede leer {pdf}: {exc!r}")
            summary.append((club.name, formats, "—", "—", "—", "—", "ilegible con pdfplumber"))
            continue
        for number, chars in enumerate(layer.chars_per_page, start=1):
            rows.append({
                "club_id": club.club_id,
                "file": pdf,
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
        summary.append((club.name, formats, layer.pages, layer.text_pages,
                        f"{min(chars)} · {statistics.median(chars):g} · {max(chars)}",
                        ", ".join(keywords) or "ninguna", layer.classification))
        per_page.append(f"{club.name}: {' '.join(str(c) for c in chars)}")

    out = PROCESSED_DIR / f"text_layer_{season_slug(season)}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print("| Club | Formato | Páginas | Págs. con texto | Caracteres por página "
          "(mín · mediana · máx) | Palabras clave | Clasificación |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in summary:
        print("| " + " | ".join(str(value) for value in row) + " |")
    print("\nCaracteres por página:")
    print("\n".join(per_page))
    images = [row[0] for row in summary if row[-1] == "imagen"]
    unreadable = [row[0] for row in summary if row[-1] == "ilegible con pdfplumber"]
    print(f"\nPDFs de imagen: {len(images)} de {len(summary)}"
          + (f" ({', '.join(images)})" if images else ""))
    if unreadable:
        print(f"Ilegibles con pdfplumber, sin clasificar: {', '.join(unreadable)}")
    print("Regla de la decisión 3: "
          + ("3 o más de imagen -> se propone OCR para esos." if len(images) >= 3
             else "menos de 3 de imagen -> los de imagen quedan como hueco."))
    print(f"Detalle por página en {out.relative_to(ROOT)}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pitch_to_balance_sheet")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("download", "descarga las cuentas de Companies House de una temporada"),
        ("text-layer", "mide la capa de texto de los PDFs descargados"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--season", default="2024/25", help="temporada, p. ej. 2024/25")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        fiscal_year_end_date(args.season, "06-30")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.command == "download":
        return download(args.season)
    return text_layer(args.season)
