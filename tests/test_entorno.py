"""Comprobaciones del entorno: versión de Python, dependencias fijadas y red bloqueada."""

import importlib.metadata
import socket
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_python_311_o_superior():
    assert sys.version_info >= (3, 11)


def test_dependencias_con_la_version_fijada():
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requisitos = config["project"]["dependencies"] + config["dependency-groups"]["dev"]
    for texto in requisitos:
        requisito = Requirement(texto)
        if requisito.marker and not requisito.marker.evaluate():
            continue  # p. ej. ocrmac, que solo se instala en macOS
        [especificador] = requisito.specifier
        assert especificador.operator == "==", texto
        assert importlib.metadata.version(requisito.name) == especificador.version, texto


def test_paquete_importable():
    import pitch_to_balance_sheet

    assert pitch_to_balance_sheet.__doc__


def test_red_bloqueada():
    with pytest.raises(RuntimeError, match="no usan la red"):
        socket.getaddrinfo("pypi.org", 443)
    with socket.socket() as s, pytest.raises(RuntimeError, match="no usan la red"):
        s.connect(("127.0.0.1", 9))
