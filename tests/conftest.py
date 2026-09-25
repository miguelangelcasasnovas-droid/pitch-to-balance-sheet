"""Configuración común de los tests.

Los tests no usan la red: trabajan con fixtures grabados en tests/fixtures/.
Cualquier intento de conexión falla con NetworkBlockedError, en local y en el CI.
"""

import socket

import pytest


class NetworkBlockedError(RuntimeError):
    """Un test intentó abrir una conexión de red."""


def _blocked(*args, **kwargs):
    raise NetworkBlockedError("Los tests no usan la red: graba la respuesta en tests/fixtures/.")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
