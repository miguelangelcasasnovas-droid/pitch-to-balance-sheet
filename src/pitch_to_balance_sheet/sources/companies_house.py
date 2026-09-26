"""Cliente de la API de Companies House: filing history y Document API.

- Autenticación básica con la clave de .env como usuario. La clave no se imprime ni se guarda.
- Como mucho 600 peticiones cada 5 minutos: al llegar al límite, se espera.
- Reintentos con espera ante 429, errores 5xx y fallos de conexión. Si se agotan, o si la
  respuesta es otro error, sale CompaniesHouseError con el motivo.
"""

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from pitch_to_balance_sheet.config import Club
from pitch_to_balance_sheet.manifest import ManifestEntry, sha256_bytes

log = logging.getLogger(__name__)

API_URL = "https://api.company-information.service.gov.uk"
DOCUMENT_API_URL = "https://document-api.company-information.service.gov.uk"
RATE_LIMIT = 600
RATE_WINDOW_S = 300.0
MAX_RETRIES = 4
BACKOFF_S = 5.0
TIMEOUT_S = 60
# Formatos que se descargan si el documento los tiene, con su extensión.
FORMATS = {"application/pdf": ".pdf", "application/xhtml+xml": ".xhtml"}


class CompaniesHouseError(RuntimeError):
    """Un paso de la descarga no se pudo completar."""


class RateLimiter:
    """Ventana deslizante: como mucho `limit` peticiones cada `window` segundos."""

    def __init__(
        self,
        limit: int = RATE_LIMIT,
        window: float = RATE_WINDOW_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._limit = limit
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()

    def wait(self) -> None:
        while True:
            now = self._clock()
            while self._calls and now - self._calls[0] >= self._window:
                self._calls.popleft()
            if len(self._calls) < self._limit:
                self._calls.append(now)
                return
            wait = self._window - (now - self._calls[0])
            log.info("Límite de %d peticiones: espera de %.0f s", self._limit, wait)
            self._sleep(wait)


class CompaniesHouseClient:
    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ):
        if not api_key:
            raise CompaniesHouseError("Falta COMPANIES_HOUSE_API_KEY en .env")
        self._session = session if session is not None else requests.Session()
        self._session.auth = (api_key, "")
        self._limiter = limiter or RateLimiter()
        self._sleep = sleep
        self._now = now

    def _get(self, url: str, *, params: dict | None = None, accept: str | None = None):
        headers = {"Accept": accept} if accept else None
        for attempt in range(MAX_RETRIES + 1):
            self._limiter.wait()
            try:
                response = self._session.get(
                    url, params=params, headers=headers, timeout=TIMEOUT_S
                )
            except requests.RequestException as exc:
                reason = f"fallo de conexión ({type(exc).__name__})"
                wait = BACKOFF_S * 2**attempt
            else:
                if response.status_code == 200:
                    return response
                if response.status_code == 429:
                    reason = "HTTP 429 (límite de peticiones)"
                    wait = self._rate_limit_wait(response, attempt)
                elif response.status_code >= 500:
                    reason = f"HTTP {response.status_code}"
                    wait = BACKOFF_S * 2**attempt
                else:
                    raise CompaniesHouseError(f"HTTP {response.status_code} en {url}")
            if attempt < MAX_RETRIES:
                log.warning(
                    "%s en %s: reintento %d de %d en %.0f s",
                    reason, url, attempt + 1, MAX_RETRIES, wait,
                )
                self._sleep(wait)
        raise CompaniesHouseError(f"{reason} en {url} tras {MAX_RETRIES} reintentos")

    def _rate_limit_wait(self, response, attempt: int) -> float:
        """Hasta el reinicio de la ventana que indica X-Ratelimit-Reset (segundos epoch)."""
        reset = response.headers.get("X-Ratelimit-Reset", "")
        if reset.isdigit():
            return min(max(float(reset) - self._now(), 1.0), RATE_WINDOW_S)
        return BACKOFF_S * 2**attempt

    def accounts_filings(self, company_number: str) -> list[dict]:
        """Todas las presentaciones de la categoría "accounts" del filing history."""
        url = f"{API_URL}/company/{company_number}/filing-history"
        items: list[dict] = []
        while True:
            params = {"category": "accounts", "items_per_page": 100, "start_index": len(items)}
            data = self._get(url, params=params).json()
            page = data.get("items") or []
            items.extend(page)
            if not page or len(items) >= data.get("total_count", 0):
                return items

    def document_metadata(self, document_id: str) -> dict:
        return self._get(f"{DOCUMENT_API_URL}/document/{document_id}").json()

    def document_content(self, content_url: str, content_type: str) -> bytes:
        return self._get(content_url, accept=content_type).content


@dataclass(frozen=True)
class AccountsDocument:
    """Cuentas de una sociedad: su presentación en Companies House y los archivos bajados."""

    club_id: str
    company_number: str
    made_up_date: str
    filing_date: str
    filing_type: str
    description: str
    pages: int | None
    paper_filed: bool | None
    document_id: str
    formats: tuple[str, ...]  # formatos del documento según sus metadatos
    files: tuple[str, ...]  # rutas relativas a data/raw/


def select_accounts(filings: list[dict], made_up_date: date) -> dict:
    """La presentación de cuentas cerradas en made_up_date. Si no hay exactamente una, error."""
    target = made_up_date.isoformat()
    matches = [
        filing
        for filing in filings
        if filing.get("category") == "accounts"
        and (filing.get("description_values") or {}).get("made_up_date") == target
    ]
    if not matches:
        raise CompaniesHouseError(f"no hay cuentas cerradas a {target} en el filing history")
    if len(matches) > 1:
        detail = "; ".join(f"{f.get('type')} del {f.get('date')}" for f in matches)
        raise CompaniesHouseError(
            f"hay {len(matches)} presentaciones de cuentas cerradas a {target} ({detail}): "
            "hay que decidir a mano cuál se usa"
        )
    return matches[0]


def document_id(filing: dict) -> str:
    link = (filing.get("links") or {}).get("document_metadata")
    if not link:
        raise CompaniesHouseError(
            f"la presentación {filing.get('transaction_id')} no tiene documento en la Document API"
        )
    return link.rstrip("/").rsplit("/", 1)[-1]


def check_content(content: bytes, content_type: str, expected_bytes: int | None) -> None:
    """Falla si el archivo no es del formato pedido o no tiene el tamaño de los metadatos."""
    head = content[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if content_type == "application/pdf" and not head.startswith(b"%pdf-"):
        raise CompaniesHouseError("la respuesta no es un PDF")
    if content_type == "application/xhtml+xml" and b"<html" not in head:
        raise CompaniesHouseError("la respuesta no es un XHTML")
    if expected_bytes is not None and len(content) != expected_bytes:
        raise CompaniesHouseError(
            f"descarga incompleta: {len(content)} bytes y los metadatos dicen {expected_bytes}"
        )


def download_accounts(
    client: CompaniesHouseClient, club: Club, made_up_date: date, raw_dir: Path
) -> tuple[AccountsDocument, list[ManifestEntry]]:
    """Descarga las cuentas cerradas en made_up_date, en PDF y en XHTML si lo hay."""
    filing = select_accounts(client.accounts_filings(club.companies_house_number), made_up_date)
    doc_id = document_id(filing)
    metadata = client.document_metadata(doc_id)
    resources = metadata.get("resources") or {}
    wanted = [content_type for content_type in FORMATS if content_type in resources]
    if not wanted:
        raise CompaniesHouseError(
            f"el documento {doc_id} no tiene PDF ni XHTML (formatos: {sorted(resources)})"
        )
    content_url = (metadata.get("links") or {}).get("document") or (
        f"{DOCUMENT_API_URL}/document/{doc_id}/content"
    )
    (raw_dir / "companies_house").mkdir(parents=True, exist_ok=True)
    stem = f"companies_house/{club.club_id}_{club.companies_house_number}_{made_up_date}"
    entries = []
    for content_type in wanted:
        content = client.document_content(content_url, content_type)
        check_content(content, content_type, resources[content_type].get("content_length"))
        relative = stem + FORMATS[content_type]
        (raw_dir / relative).write_bytes(content)
        entries.append(
            ManifestEntry(
                file=relative,
                url=content_url,
                retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
                sha256=sha256_bytes(content),
                bytes=len(content),
                content_type=content_type,
            )
        )
    document = AccountsDocument(
        club_id=club.club_id,
        company_number=club.companies_house_number,
        made_up_date=made_up_date.isoformat(),
        filing_date=filing.get("date", ""),
        filing_type=filing.get("type", ""),
        description=filing.get("description", ""),
        pages=filing.get("pages"),
        paper_filed=filing.get("paper_filed"),
        document_id=doc_id,
        formats=tuple(sorted(resources)),
        files=tuple(entry.file for entry in entries),
    )
    return document, entries
