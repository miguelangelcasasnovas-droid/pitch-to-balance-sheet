"""Línea de comandos: python -m pitch_to_balance_sheet <comando>.

- download: cuentas de Companies House de las fuentes que lo usan, a data/raw/companies_house/.
- download-web: PDFs de la web de los clubes (fuentes url), a data/raw/web/.
- download-fx: tipos de referencia diarios del BCE de las monedas de los clubes que no informan
  en EUR o no cotizan en EUR, a data/raw/ecb/.
- register-manual: PDFs descargados a mano y el CSV de precios de config/market.yaml, al
  manifiesto.
- text-layer: capa de texto de los PDFs locales, a data/processed/text_layer_<temporada>.csv.
- extract: cifras de la cuenta de resultados y del balance de cada club, con cuadres y recortes.
  Lee el OCR guardado; con --reocr vuelve a pasar Apple Vision (solo macOS).
- facts: fact_financials en EUR con los tipos del BCE, validada con pandera, a
  data/processed/fact_financials.parquet y football.duckdb; y las métricas en EUR.
- valuation: métricas y valoración por comparables a la fecha de valoración, a las tablas
  metrics y valuation de football.duckdb.

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

from pitch_to_balance_sheet import facts, fx, manifest, market, metrics, report, valuation
from pitch_to_balance_sheet.config import (
    PROCESSED_DIR,
    RAW_DIR,
    ROOT,
    fiscal_year_end_date,
    load_clubs,
    season_slug,
)
from pitch_to_balance_sheet.extract import run
from pitch_to_balance_sheet.extract.clubs import SPECS
from pitch_to_balance_sheet.extract.text_layer import KEYWORDS, column_name, measure
from pitch_to_balance_sheet.sources import web
from pitch_to_balance_sheet.sources.companies_house import (
    AccountsDocument,
    CompaniesHouseClient,
    CompaniesHouseError,
    download_accounts,
)
from pitch_to_balance_sheet.sources.config import load_sources
from pitch_to_balance_sheet.sources.local import MANIFEST, filings_path, local_pdf

log = logging.getLogger(__name__)

SOURCE_NAMES = {"companies_house": "Companies House", "manual": "manual", "url": "web del club"}


def download(season: str) -> int:
    load_dotenv(ROOT / ".env")
    try:
        client = CompaniesHouseClient(os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip())
    except CompaniesHouseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sources = load_sources(season)
    documents = []
    for club in load_clubs():
        club_sources = sources.get(club.club_id)
        if club_sources is None or all(s.kind != "companies_house" for s in club_sources.all):
            continue
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


def download_web(season: str) -> int:
    """Descarga los archivos de la web (fuentes url) que falten y los registra en el manifiesto."""
    errors = []
    for club_id, club_sources in load_sources(season).items():
        for source in club_sources.all:
            if source.kind != "url":
                continue
            if (RAW_DIR / source.file).exists():
                try:
                    manifest.verify(RAW_DIR, source.file, MANIFEST)
                except manifest.ManifestError as exc:
                    errors.append(f"{club_id}: {exc}")
                else:
                    log.info("%s: data/raw/%s ya descargado y con su sha256", club_id,
                             source.file)
                continue
            try:
                entry = web.download_file(source.url, RAW_DIR, source.file)
            except web.WebDownloadError as exc:
                errors.append(f"{club_id}: {exc}")
                continue
            manifest.upsert(MANIFEST, [entry])
            log.info("%s: data/raw/%s  %d bytes  sha256 %s", club_id, entry.file, entry.bytes,
                     entry.sha256)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def download_fx(season: str) -> int:
    """Descarga la serie diaria del BCE de cada moneda que no es EUR, desde el primer día del año
    fiscal que antes empieza hasta el último cierre, y la registra en el manifiesto."""
    windows = [fx.fiscal_year(season, club.fiscal_year_end) for club in load_clubs()
               if club.club_id in SPECS]
    start, end = min(w[0] for w in windows), max(w[1] for w in windows)
    errors = []
    quoted = {market.iso_currency(club.quote_currency) for club in load_clubs()
              if club.quote_currency}
    for currency in sorted(({spec.currency for spec in SPECS.values()} | quoted) - {fx.BASE}):
        file = fx.rates_file(currency, season)
        if (RAW_DIR / file).exists():
            try:
                manifest.verify(RAW_DIR, file, MANIFEST)
            except manifest.ManifestError as exc:
                errors.append(str(exc))
            else:
                log.info("%s: data/raw/%s ya descargado y con su sha256", currency, file)
            continue
        try:
            entry = web.download_file(fx.download_url(currency, start, end), RAW_DIR, file)
            rates = fx.load_rates(RAW_DIR / file, currency)
        except (web.WebDownloadError, fx.FxError) as exc:
            errors.append(f"{currency}: {exc}")
            continue
        manifest.upsert(MANIFEST, [entry])
        log.info("%s: data/raw/%s  %d tipos del %s al %s  sha256 %s", currency, file,
                 len(rates), min(rates), max(rates), entry.sha256)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def register_manual(season: str) -> int:
    """Registra en el manifiesto los PDFs manuales de config/sources.yaml y el CSV de precios de
    config/market.yaml."""
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
    return register_prices(season, registered)


def register_prices(season: str, registered: dict) -> int:
    """El CSV de precios bajados a mano: se comprueba entero antes de registrarlo."""
    try:
        config = market.load_config(season)
        path = RAW_DIR / config.prices_file
        prices = market.load_prices(path, load_clubs(), config)
    except market.MarketError as exc:
        print(f"error: precios: {exc}", file=sys.stderr)
        return 1
    sha256 = manifest.sha256_file(path)
    previous = registered.get(config.prices_file)
    if previous and previous["sha256"] != sha256:
        print(f"error: precios: data/raw/{config.prices_file} ha cambiado desde que se registró "
              f"(sha256 {previous['sha256']} y ahora {sha256}). Si es a propósito, quita su fila "
              "del manifiesto y vuelve a registrarlo", file=sys.stderr)
        return 1
    if previous:
        log.info("precios: data/raw/%s ya estaba registrado", config.prices_file)
        return 0
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    entry = manifest.ManifestEntry(
        file=config.prices_file,
        # Cada precio lleva su fuente en el propio CSV (source_url, source_name, retrieved_at).
        url="manual: fuente de cada precio en su fila (source_url)",
        retrieved_at=modified.isoformat(timespec="seconds"),
        sha256=sha256,
        bytes=path.stat().st_size,
        content_type="text/csv",
    )
    manifest.upsert(MANIFEST, [entry])
    log.info("precios: registrado data/raw/%s con %d tickers  sha256 %s", entry.file,
             len(prices), entry.sha256)
    return 0


def _pages_summary(pages: tuple[int, ...]) -> str:
    shown = ", ".join(str(page) for page in pages[:3])
    return f"p. {shown}{', …' if len(pages) > 3 else ''}"


def text_layer(season: str) -> int:
    names = {club.club_id: club.name for club in load_clubs()}
    rows, summary, per_page, errors, not_downloaded, not_pdf = [], [], [], [], [], []
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
            if not pdf.lower().endswith(".pdf"):
                not_pdf.append(f"{label} ({pdf})")
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
                    **{column_name(term): number in layer.keyword_pages[term]
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
    if not_pdf:
        print(f"\nSin medir, no es un PDF (paquete ESEF, se lee con el lector de iXBRL): "
              f"{', '.join(not_pdf)}")
    if rows:
        print(f"Detalle por página en {out.relative_to(ROOT)}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


def extract(season: str, club_id: str | None, reocr: bool = False) -> int:
    """Tres cifras por club, con cuadres, controles y recortes. Un club en error no para a
    los demás."""
    if club_id is not None and club_id not in SPECS:
        print(f"error: no hay extractor para {club_id}", file=sys.stderr)
        return 1
    results = []
    for spec in SPECS.values():
        if club_id is not None and spec.club_id != club_id:
            continue
        result = run.extract_club(season, spec, reocr)
        results.append(result)
        print(f"\n== {spec.club_id} · {result.source or '—'} · {result.pdf or '—'}")
        for figure in result.figures:
            print(f"  {figure.concept}: {figure.value:,} ({figure.unit or spec.unit}, "
                  f"{spec.currency})"
                  + (" · derivada" if figure.is_derived else "")
                  + f" · {figure.sources} · {figure.ocr_note}"
                  + (f" · {result.crops[figure.concept]}" if figure.concept in result.crops
                     else ""))
            if figure.note:
                print(f"    nota: {figure.note}")
        passed = sum(check.ok for check in result.checks)
        if result.checks or not result.error:
            rounded = f", {len(result.rounded)} por redondeo" if result.rounded else ""
            print(f"  cuadres: {passed} de {len(result.checks)} OK{rounded}")
            for check in result.rounded:
                print(f"  redondeo {check.document} pág. {check.page} [{check.column}] "
                      f"{check.relation}: {check.reported:,} frente a {check.computed:,} "
                      f"(diferencia {check.difference:,}, {check.rows} filas, tolerancia "
                      f"{check.tolerance})")
        else:
            print("  cuadres: no se han hecho (el club está en error)")
        for check in result.failed:
            print(f"  FALLA {check.document} pág. {check.page} [{check.column}] {check.relation}: "
                  f"{check.reported:,} frente a {check.computed:,} "
                  f"(diferencia {check.difference:,}, {check.rows} filas, tolerancia "
                  f"{check.tolerance})")
        for restatement in result.restatements:
            print(f"  {'REEXPRESIÓN' if restatement.restated else 'reexpresión no'} "
                  f"{restatement.document} {restatement.concept}: {restatement.primary:,} frente "
                  f"a {restatement.control:,} ({restatement.pct:.2f}%)")
        for note in result.corrections:
            print(f"  corrección: {note}")
        if result.error:
            sys.stdout.flush()  # que el error no caiga en mitad de la salida del club
            print(f"error: {spec.club_id}: {result.error}", file=sys.stderr)
    written = run.write_outputs(season, results)
    print("\n" + run.table(results))
    # Reparto de ingresos (fase 3a), validado con pandera. Un club sin sus partidas en
    # config/line_items.yaml es un error.
    try:
        frame = run.mix_frame(results)
    except ValueError as exc:
        print(f"error: reparto de ingresos: {exc}", file=sys.stderr)
        return 1
    problems = run.validate_mix(frame)
    print("\n" + run.mix_table(results, frame))
    print("\n" + run.balance_table(results))
    for problem in problems:
        print(f"error: reparto de ingresos (pandera): {problem}", file=sys.stderr)
    for path in written:
        print(f"\n{path}", end="")
    print()
    return 1 if problems or any(result.error for result in results) else 0


def build_facts(season: str) -> int:
    """fact_financials en EUR a partir de las cifras de extract y los tipos del BCE, validada
    con pandera; y la tabla resumen en EUR."""
    try:
        frame = facts.build(season)
    except (facts.FactsError, fx.FxError, manifest.ManifestError) as exc:
        print(f"error: fact_financials: {exc}", file=sys.stderr)
        return 1
    problems = facts.validate(frame)
    if problems:
        for problem in problems:
            print(f"error: fact_financials (pandera): {problem}", file=sys.stderr)
        return 1
    metric_frame = metrics.to_frame(metrics.compute(frame))
    problems = metrics.validate(metric_frame)
    if problems:
        for problem in problems:
            print(f"error: métricas (pandera): {problem}", file=sys.stderr)
        return 1
    written = facts.write(frame, season)
    facts.replace_season(written[1], "metrics", metric_frame, season)
    counts = frame.groupby("is_gap").size().to_dict()
    print(f"fact_financials {season}: {len(frame)} filas, {counts.get(False, 0)} cifras y "
          f"{counts.get(True, 0)} huecos; pandera OK. Métricas: {len(metric_frame)} "
          f"({(metric_frame['status'] == 'ok').sum()} con valor), en la tabla metrics.")
    print("\n" + report.metrics_table(metric_frame))
    for path in written:
        print(f"\n{path.relative_to(ROOT)}", end="")
    print()
    return 0


def run_valuation(season: str) -> int:
    """Valoración por comparables de la temporada, a la tabla valuation. Los precios salen del
    CSV manual de config/market.yaml, registrado en el manifiesto."""
    try:
        frame = facts.read(season)
        problems = facts.validate(frame)
        if problems:
            raise facts.FactsError("fact_financials no pasa pandera: " + "; ".join(problems))
        metric_frame = metrics.to_frame(metrics.compute(frame))
        config = market.load_config(season)
        clubs = load_clubs()
        path = RAW_DIR / config.prices_file
        if not path.exists():
            raise market.MarketError(market.missing_file_message(path, clubs, config))
        manifest.verify(RAW_DIR, config.prices_file, MANIFEST)
        prices = market.load_prices(path, clubs, config)
        rates, quotes = {}, {}
        for club in clubs:
            if not club.ticker:
                continue
            price = prices[club.club_id]
            if price.currency != fx.BASE and price.currency not in rates:
                rates_file = fx.rates_file(price.currency, season)
                manifest.verify(RAW_DIR, rates_file, MANIFEST)
                rates[price.currency] = fx.load_rates(RAW_DIR / rates_file, price.currency)
            shares = frame[(frame["club_id"] == club.club_id)
                           & (frame["concept"] == "shares_outstanding")]
            if shares.empty or shares.iloc[0]["is_gap"]:
                raise valuation.ValuationError(f"{club.club_id}: falta shares_outstanding")
            quotes[club.club_id] = valuation.quote(club, price, int(shares.iloc[0]["value_full"]),
                                                   rates)
        valuation_frame = valuation.to_frame(
            valuation.run(frame, metric_frame, quotes, config.valuation_date, season))
        problems = valuation.validate(valuation_frame)
        if problems:
            raise valuation.ValuationError("la valoración no pasa pandera: " + "; ".join(problems))
        database = PROCESSED_DIR / facts.DATABASE
        facts.replace_season(database, "valuation", valuation_frame, season)
    except (facts.FactsError, fx.FxError, manifest.ManifestError, market.MarketError,
            valuation.ValuationError) as exc:
        print(f"error: valoración: {exc}", file=sys.stderr)
        return 1
    print(f"Valoración {season}: {len(valuation_frame)} filas; pandera OK. En millones de EUR.")
    print("\n" + report.final_table(valuation_frame, metric_frame))
    print("\n" + report.listed_table(valuation_frame))
    print("\n" + report.sensitivity_table(valuation_frame))
    print("\n" + report.backtest_table(valuation_frame))
    print(f"\n{database.relative_to(ROOT)}: tabla valuation")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pitch_to_balance_sheet")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("download", "descarga las cuentas de Companies House de una temporada"),
        ("download-web", "descarga los PDFs de la web de los clubes (fuentes url)"),
        ("download-fx", "descarga los tipos de referencia diarios del BCE (monedas no EUR)"),
        ("register-manual", "registra en el manifiesto los PDFs y los precios bajados a mano"),
        ("text-layer", "mide la capa de texto de los PDFs locales de config/sources.yaml"),
        ("extract", "cifras de la cuenta de resultados y del balance, con cuadres y recortes"),
        ("facts", "fact_financials en EUR (parquet y DuckDB) y las métricas, validadas"),
        ("valuation", "valoración por comparables, con los precios manuales, a la tabla valuation"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--season", default="2024/25", help="temporada, p. ej. 2024/25")
        if name == "extract":
            command.add_argument("--club", help="club_id, p. ej. chelsea (todos si se omite)")
            command.add_argument("--reocr", action="store_true",
                                 help="vuelve a pasar Apple Vision (solo macOS); sin esta opción "
                                      "se lee el OCR guardado en data/interim/ocr/")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        fiscal_year_end_date(args.season, "06-30")
        load_sources(args.season)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.command == "extract":
        return extract(args.season, args.club, args.reocr)
    commands_by_name = {
        "download": download,
        "download-web": download_web,
        "download-fx": download_fx,
        "register-manual": register_manual,
        "text-layer": text_layer,
        "facts": build_facts,
        "valuation": run_valuation,
    }
    return commands_by_name[args.command](args.season)
