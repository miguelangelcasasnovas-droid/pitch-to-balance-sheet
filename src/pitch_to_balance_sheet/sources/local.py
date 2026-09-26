"""PDF local de cada fuente, comprobado contra el manifiesto antes de usarlo."""

import csv

from pitch_to_balance_sheet import manifest
from pitch_to_balance_sheet.config import PROCESSED_DIR, RAW_DIR, season_slug
from pitch_to_balance_sheet.sources.config import Source, load_sources

MANIFEST = RAW_DIR / "manifest.csv"


def filings_path(season: str):
    return PROCESSED_DIR / f"companies_house_filings_{season_slug(season)}.csv"


def local_pdf(season: str, club_id: str, source: Source) -> str | None:
    """PDF local de una fuente, comprobado contra el manifiesto. None si es una URL sin bajar.

    Sale ManifestError si falta el archivo, no está registrado o su sha256 ha cambiado.
    """
    if source.kind == "url":
        if not (RAW_DIR / source.file).exists():
            return None
        manifest.verify(RAW_DIR, source.file, MANIFEST)
        return source.file
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


def document_file(season: str, club_id: str, control_index: int | None) -> tuple[Source, str, str]:
    """Fuente, PDF (relativo a data/raw/) y sha256 de la fuente principal o de un control."""
    club_sources = load_sources(season)[club_id]
    source = (club_sources.primary if control_index is None
              else club_sources.controls[control_index])
    pdf = local_pdf(season, club_id, source)
    if pdf is None:
        raise manifest.ManifestError(
            f"{source.url} todavía sin descargar. Ejecuta antes: "
            "python -m pitch_to_balance_sheet download-web"
        )
    return source, pdf, manifest.read(MANIFEST)[pdf]["sha256"]
