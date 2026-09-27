"""Descarga de los archivos de la web: fuentes `url` de config/sources.yaml.

Antes de descargar se lee el robots.txt del dominio (RFC 9309): si responde 4xx no hay
restricciones; si responde 5xx o no se puede leer, se supone que todo está prohibido; si
responde 200, se aplican sus reglas. Si no se permite, WebDownloadError y hay que descargarlo a
mano. Cada archivo tiene que ser del formato de su extensión (un PDF, o un ZIP como los
paquetes ESEF) y se registra en el manifiesto con su URL, fecha y sha256.
"""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from pitch_to_balance_sheet.manifest import ManifestEntry, sha256_bytes

log = logging.getLogger(__name__)

USER_AGENT = "pitch-to-balance-sheet/0.1 (analisis de cuentas publicas de clubes)"
ROBOTS_AGENT = "pitch-to-balance-sheet"
ATTEMPTS = 3
BACKOFF_S = 5.0
TIMEOUT_S = 120
# Extensión -> (firma con la que empieza el archivo, content_type del manifiesto).
FORMATS = {".pdf": (b"%PDF-", "application/pdf"), ".zip": (b"PK\x03\x04", "application/zip")}


class WebDownloadError(RuntimeError):
    """Un archivo de la web no se pudo descargar o no es del formato esperado."""


def robots_allows(url: str, session=None) -> tuple[bool, str]:
    """¿Permite el robots.txt del dominio descargar esta URL? Devuelve también el motivo."""
    session = session or requests.Session()
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = session.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as exc:
        return False, (f"{robots_url} no se pudo leer ({type(exc).__name__}): se supone que "
                       "todo está prohibido (RFC 9309, 2.3.1.4)")
    if 400 <= response.status_code < 500:
        return True, (f"{robots_url} responde {response.status_code}: sin restricciones "
                      "(RFC 9309, 2.3.1.3)")
    if response.status_code >= 500:
        return False, (f"{robots_url} responde {response.status_code}: se supone que todo está "
                       "prohibido (RFC 9309, 2.3.1.4)")
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch(ROBOTS_AGENT, url)
    return allowed, f"{robots_url} {'permite' if allowed else 'no permite'} esta ruta"


def download_file(url: str, raw_dir: Path, file: str, session=None,
                  sleep=time.sleep) -> ManifestEntry:
    suffix = Path(file).suffix.lower()
    if suffix not in FORMATS:
        raise WebDownloadError(f"{file}: formato {suffix!r} no previsto; se esperan "
                               f"{', '.join(FORMATS)}")
    signature, content_type = FORMATS[suffix]
    session = session or requests.Session()
    allowed, why = robots_allows(url, session)
    if not allowed:
        raise WebDownloadError(f"{why}: hay que descargarlo a mano")
    log.info("%s", why)
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
    if not content.startswith(signature):
        raise WebDownloadError(f"{url} no devolvió un {suffix[1:].upper()}")
    path = raw_dir / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return ManifestEntry(
        file=file,
        url=url,
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        sha256=sha256_bytes(content),
        bytes=len(content),
        content_type=content_type,
    )
