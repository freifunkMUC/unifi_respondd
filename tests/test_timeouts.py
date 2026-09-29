#!/usr/bin/env python3
"""Unit tests for unified_respondd/timeouts.py module."""

import socket
import threading

import pytest
import requests

from unified_respondd.timeouts import set_default_request_timeout


@pytest.fixture
def restore_requests():
    request = requests.Session.request
    yield
    requests.Session.request = request


@pytest.fixture
def hanging_server():
    """A server that accepts connections but never answers, like a hung controller."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    connections = []
    threading.Thread(
        target=lambda: connections.extend(server.accept() for _ in range(5)),
        daemon=True,
    ).start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}/"
    for connection, _ in connections:
        connection.close()
    server.close()


def test_hanging_request_times_out(restore_requests, hanging_server):
    set_default_request_timeout(0.2)
    with pytest.raises(requests.exceptions.Timeout):
        requests.Session().get(hanging_server)


def test_explicit_timeout_wins(restore_requests, hanging_server):
    set_default_request_timeout(60)
    with pytest.raises(requests.exceptions.Timeout):
        requests.get(hanging_server, timeout=0.2)


def test_setting_twice_does_not_stack(restore_requests):
    set_default_request_timeout(1)
    set_default_request_timeout(2)
    assert requests.Session.request.default_timeout == 2
    assert not hasattr(requests.Session.request.__wrapped__, "default_timeout")
