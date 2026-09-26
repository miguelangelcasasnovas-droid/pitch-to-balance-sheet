"""Cliente de Companies House con respuestas simuladas: sin red y sin la clave real."""

import hashlib
from datetime import date

import pytest
import requests

from pitch_to_balance_sheet.config import Club
from pitch_to_balance_sheet.sources.companies_house import (
    MAX_RETRIES,
    CompaniesHouseClient,
    CompaniesHouseError,
    RateLimiter,
    download_accounts,
    select_accounts,
)

KEY = "clave-de-prueba"
PDF = b"%PDF-1.4\ncontenido de prueba"
XHTML = b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"></html>'
DOC_URL = "https://document-api.company-information.service.gov.uk/document/DOC1"
CLUB = Club("club", "Club", "Club Limited", "01234567", "06-30")


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._json


class FakeSession:
    """Devuelve las respuestas en orden y guarda cada petición."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.auth = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append({"url": url, "params": params, "headers": headers})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client(responses):
    session = FakeSession(responses)
    sleeps = []
    client = CompaniesHouseClient(KEY, session=session, sleep=sleeps.append, now=lambda: 1000.0)
    return client, session, sleeps


def filing(made_up_date, filing_type="AA"):
    return {
        "category": "accounts",
        "type": filing_type,
        "date": "2026-03-01",
        "description": "accounts-with-accounts-type-group",
        "description_values": {"made_up_date": made_up_date},
        "pages": 1,
        "paper_filed": True,
        "transaction_id": "T1",
        "links": {"document_metadata": DOC_URL},
    }


def metadata(resources):
    return {"resources": resources, "links": {"document": f"{DOC_URL}/content"}}


def test_elige_las_cuentas_del_cierre_pedido():
    filings = [filing("2024-06-30"), filing("2025-06-30")]
    chosen = select_accounts(filings, date(2025, 6, 30))
    assert chosen["description_values"]["made_up_date"] == "2025-06-30"


def test_sin_cuentas_del_cierre_es_error():
    with pytest.raises(CompaniesHouseError, match="no hay cuentas cerradas a 2025-06-30"):
        select_accounts([filing("2024-06-30")], date(2025, 6, 30))


def test_dos_presentaciones_del_mismo_cierre_es_error():
    filings = [filing("2025-06-30"), filing("2025-06-30", "AAMD")]
    with pytest.raises(CompaniesHouseError, match="hay 2 presentaciones"):
        select_accounts(filings, date(2025, 6, 30))


def test_429_espera_al_reinicio_de_la_ventana_y_reintenta():
    client, _, sleeps = make_client([
        FakeResponse(429, headers={"X-Ratelimit-Reset": "1030"}),
        FakeResponse(json_data={"resources": {}}),
    ])
    assert client.document_metadata("DOC1") == {"resources": {}}
    assert sleeps == [30.0]


def test_fallo_de_conexion_se_reintenta():
    client, _, sleeps = make_client([
        requests.ConnectionError("sin conexión"),
        FakeResponse(json_data={"resources": {}}),
    ])
    assert client.document_metadata("DOC1") == {"resources": {}}
    assert sleeps == [5.0]


def test_5xx_agota_los_reintentos_y_falla():
    client, session, sleeps = make_client([FakeResponse(503)] * (MAX_RETRIES + 1))
    with pytest.raises(CompaniesHouseError, match=f"HTTP 503 .* tras {MAX_RETRIES} reintentos"):
        client.document_metadata("DOC1")
    assert len(session.requests) == MAX_RETRIES + 1
    assert sleeps == [5.0, 10.0, 20.0, 40.0]


def test_404_falla_sin_reintentar_y_sin_mostrar_la_clave():
    client, session, _ = make_client([FakeResponse(404)])
    with pytest.raises(CompaniesHouseError, match="HTTP 404") as error:
        client.document_metadata("DOC1")
    assert len(session.requests) == 1
    assert session.auth == (KEY, "")
    assert KEY not in str(error.value)


def test_sin_clave_es_error():
    with pytest.raises(CompaniesHouseError, match="Falta COMPANIES_HOUSE_API_KEY"):
        CompaniesHouseClient("")


def test_limite_de_peticiones_espera_a_que_se_libere_la_ventana():
    clock = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    limiter = RateLimiter(limit=3, window=10.0, clock=lambda: clock[0], sleep=sleep)
    for _ in range(4):
        limiter.wait()
    assert sleeps == [10.0]


def test_descarga_el_pdf_y_lo_registra(tmp_path):
    client, session, _ = make_client([
        FakeResponse(json_data={"items": [filing("2025-06-30")], "total_count": 1}),
        FakeResponse(json_data=metadata({"application/pdf": {"content_length": len(PDF)}})),
        FakeResponse(content=PDF),
    ])
    document, entries = download_accounts(client, CLUB, date(2025, 6, 30), tmp_path)

    assert document.formats == ("application/pdf",)
    assert document.files == ("companies_house/club_01234567_2025-06-30.pdf",)
    assert (tmp_path / document.files[0]).read_bytes() == PDF
    assert session.requests[-1]["headers"] == {"Accept": "application/pdf"}
    [entry] = entries
    assert entry.url == f"{DOC_URL}/content"
    assert entry.sha256 == hashlib.sha256(PDF).hexdigest()
    assert entry.bytes == len(PDF)


def test_si_hay_xhtml_tambien_se_descarga(tmp_path):
    client, _, _ = make_client([
        FakeResponse(json_data={"items": [filing("2025-06-30")], "total_count": 1}),
        FakeResponse(json_data=metadata({
            "application/pdf": {"content_length": len(PDF)},
            "application/xhtml+xml": {"content_length": len(XHTML)},
        })),
        FakeResponse(content=PDF),
        FakeResponse(content=XHTML),
    ])
    document, entries = download_accounts(client, CLUB, date(2025, 6, 30), tmp_path)
    assert [entry.content_type for entry in entries] == ["application/pdf", "application/xhtml+xml"]
    assert (tmp_path / document.files[1]).read_bytes() == XHTML


@pytest.mark.parametrize(
    ("content", "content_length", "message"),
    [
        (b"<html>error</html>", None, "no es un PDF"),
        (PDF[:10], len(PDF), "descarga incompleta"),
    ],
)
def test_descarga_no_valida_es_error(tmp_path, content, content_length, message):
    client, _, _ = make_client([
        FakeResponse(json_data={"items": [filing("2025-06-30")], "total_count": 1}),
        FakeResponse(json_data=metadata({"application/pdf": {"content_length": content_length}})),
        FakeResponse(content=content),
    ])
    with pytest.raises(CompaniesHouseError, match=message):
        download_accounts(client, CLUB, date(2025, 6, 30), tmp_path)
    assert not list((tmp_path / "companies_house").iterdir())
