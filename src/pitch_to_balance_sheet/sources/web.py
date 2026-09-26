"""Descarga de los PDFs de la web de los clubes: fuentes `url` de config/sources.yaml.

Solo URLs cuyo robots.txt permite la descarga automática, comprobado en
docs/fuentes-pendientes.md. Cada archivo tiene que ser un PDF y se registra en el manifiesto con
su URL, fecha y sha256. Si la descarga falla, WebDownloadError con el motivo.
"""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from pitch_to_balance_sheet.manifest import ManifestEntry, sha256_bytes

log = logging.getLogger(__name__)

USER_AGENT = "pitch-to-balance-sheet/0.1 (analisis de cuentas publicas de clubes)"
ATTEMPTS = 3
BACKOFF_S = 5.0
TIMEOUT_S = 120


class WebDownloadError(RuntimeError):
    """Un PDF de la web no se pudo descargar o no es un PDF."""


def download_pdf(url: str, raw_dir: Path, file: str, session=None,
                 sleep=time.sleep) -> ManifestEntry:
    session = session or requests.Session()
    reason = ""
    for attempt in range(ATTEMPTS):
        try:
            response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
        except requests.RequestException as exc:
            reason = f"fallo de conexión ({type(exc).__name__})"
        else:
            if response.status_code == 200:
                break
            reason = f"HTTP {response.status_code}"
            if response.status_code < 500:
                raise WebDownloadError(f"{reason} en {url}")
        if attempt < ATTEMPTS - 1:
            log.warning("%s en %s: reintento en %.0f s", reason, url, BACKOFF_S * 2**attempt)
            sleep(BACKOFF_S * 2**attempt)
    else:
        raise WebDownloadError(f"{reason} en {url} tras {ATTEMPTS} intentos")
    content = response.content
    if not content.startswith(b"%PDF-"):
        raise WebDownloadError(f"{url} no devolvió un PDF")
    path = raw_dir / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return ManifestEntry(
        file=file,
        url=url,
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        sha256=sha256_bytes(content),
        bytes=len(content),
        content_type="application/pdf",
    )
