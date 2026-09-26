"""Descarga de los PDFs de la web con respuestas simuladas: sin red."""

import hashlib

import pytest
import requests

from pitch_to_balance_sheet.sources.web import ATTEMPTS, WebDownloadError, download_pdf

URL = "https://ejemplo.invalid/cuentas.pdf"
PDF = b"%PDF-1.7\ncontenido de prueba"


class FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_descarga_el_pdf_y_devuelve_su_entrada_del_manifiesto(tmp_path):
    session = FakeSession([FakeResponse(content=PDF)])
    entry = download_pdf(URL, tmp_path, "web/x.pdf", session=session)
    assert (tmp_path / "web" / "x.pdf").read_bytes() == PDF
    assert (entry.url, entry.sha256, entry.bytes) == (URL, hashlib.sha256(PDF).hexdigest(),
                                                      len(PDF))


def test_404_es_error_sin_reintentar(tmp_path):
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(WebDownloadError, match="HTTP 404"):
        download_pdf(URL, tmp_path, "web/x.pdf", session=session)
    assert session.calls == 1


def test_errores_de_servidor_se_reintentan_y_al_final_es_error(tmp_path):
    sleeps = []
    session = FakeSession([requests.ConnectionError("sin red")] + [FakeResponse(503)] * 2)
    with pytest.raises(WebDownloadError, match=f"tras {ATTEMPTS} intentos"):
        download_pdf(URL, tmp_path, "web/x.pdf", session=session, sleep=sleeps.append)
    assert sleeps == [5.0, 10.0]


def test_lo_que_no_es_un_pdf_es_error(tmp_path):
    session = FakeSession([FakeResponse(content=b"<html>Access denied</html>")])
    with pytest.raises(WebDownloadError, match="no devolvió un PDF"):
        download_pdf(URL, tmp_path, "web/x.pdf", session=session)
    assert not (tmp_path / "web" / "x.pdf").exists()
