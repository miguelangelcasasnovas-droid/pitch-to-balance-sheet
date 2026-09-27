"""Descarga de los PDFs de la web con respuestas simuladas: sin red."""

import hashlib

import pytest
import requests

from pitch_to_balance_sheet.sources.web import (
    ATTEMPTS,
    WebDownloadError,
    download_file,
    robots_allows,
)

URL = "https://ejemplo.invalid/docs/cuentas.pdf"
PDF = b"%PDF-1.7\ncontenido de prueba"


class FakeResponse:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeSession:
    """Responde al robots.txt con `robots` y al resto con las respuestas en orden."""

    def __init__(self, responses, robots=None):
        self.responses = list(responses)
        self.robots = robots if robots is not None else FakeResponse(404)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            if isinstance(self.robots, Exception):
                raise self.robots
            return self.robots
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_descarga_el_pdf_y_devuelve_su_entrada_del_manifiesto(tmp_path):
    session = FakeSession([FakeResponse(content=PDF)])
    entry = download_file(URL, tmp_path, "web/x.pdf", session=session)
    assert (tmp_path / "web" / "x.pdf").read_bytes() == PDF
    assert (entry.url, entry.sha256, entry.bytes) == (URL, hashlib.sha256(PDF).hexdigest(),
                                                      len(PDF))
    assert session.calls == ["https://ejemplo.invalid/robots.txt", URL]


def test_404_es_error_sin_reintentar(tmp_path):
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(WebDownloadError, match="HTTP 404"):
        download_file(URL, tmp_path, "web/x.pdf", session=session)
    assert session.calls.count(URL) == 1


def test_errores_de_servidor_se_reintentan_y_al_final_es_error(tmp_path):
    sleeps = []
    session = FakeSession([requests.ConnectionError("sin red")] + [FakeResponse(503)] * 2)
    with pytest.raises(WebDownloadError, match=f"tras {ATTEMPTS} intentos"):
        download_file(URL, tmp_path, "web/x.pdf", session=session, sleep=sleeps.append)
    assert sleeps == [5.0, 10.0]


def test_lo_que_no_es_un_pdf_es_error(tmp_path):
    session = FakeSession([FakeResponse(content=b"<html>Access denied</html>")])
    with pytest.raises(WebDownloadError, match="no devolvió un PDF"):
        download_file(URL, tmp_path, "web/x.pdf", session=session)
    assert not (tmp_path / "web" / "x.pdf").exists()


@pytest.mark.parametrize(
    ("robots", "allowed", "reason"),
    [
        (FakeResponse(404), True, "sin restricciones"),
        (FakeResponse(403), True, "sin restricciones"),  # RFC 9309: 4xx, sin restricciones
        (FakeResponse(503), False, "se supone que todo está prohibido"),
        (requests.ConnectionError("sin red"), False, "no se pudo leer"),
        (FakeResponse(200, text="User-agent: *\nDisallow: /docs/\n"), False, "no permite"),
        (FakeResponse(200, text="User-agent: *\nDisallow: /privado/\n"), True, "permite"),
    ],
)
def test_robots_txt(robots, allowed, reason):
    ok, why = robots_allows(URL, FakeSession([], robots=robots))
    assert ok is allowed and reason in why


def test_si_robots_txt_no_lo_permite_no_se_descarga(tmp_path):
    session = FakeSession([FakeResponse(content=PDF)],
                          robots=FakeResponse(200, text="User-agent: *\nDisallow: /\n"))
    with pytest.raises(WebDownloadError, match="hay que descargarlo a mano"):
        download_file(URL, tmp_path, "web/x.pdf", session=session)
    assert URL not in session.calls


def test_un_zip_tiene_que_empezar_por_la_firma_de_zip(tmp_path):
    zipped = b"PK\x03\x04" + b"contenido"
    entry = download_file(URL, tmp_path, "web/x.zip", session=FakeSession([FakeResponse(
        content=zipped)]))
    assert (entry.content_type, entry.bytes) == ("application/zip", len(zipped))
    with pytest.raises(WebDownloadError, match="no devolvió un ZIP"):
        download_file(URL, tmp_path, "web/y.zip", session=FakeSession([FakeResponse(
            content=PDF)]))


def test_una_extension_no_prevista_es_error_antes_de_descargar(tmp_path):
    session = FakeSession([FakeResponse(content=PDF)])
    with pytest.raises(WebDownloadError, match="formato '.html' no previsto"):
        download_file(URL, tmp_path, "web/x.html", session=session)
    assert session.calls == []
