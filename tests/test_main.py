#!/usr/bin/env python3
"""Unit tests for unified_respondd/__main__.py module."""

import json
from unittest.mock import Mock, patch

import pytest

from tests.test_respondd_client import make_ap
from unified_respondd import __main__ as cli
from unified_respondd.config import Controller
from unified_respondd.model import Accesspoints


@pytest.fixture
def backend():
    with (
        patch.object(cli.config, "load_config", return_value={}),
        patch.object(cli.config.Config, "from_dict") as from_dict,
        patch("unified_respondd.respondd_client.backends.load") as load,
        patch("unified_respondd.respondd_client.socket.socket"),
    ):
        from_dict.return_value.controllers = [
            Controller("unifi", "unifi", Mock()),
            Controller("omada", "omada", Mock()),
        ]
        yield load.return_value


def test_dry_run_prints_nodes(backend, capsys):
    backend.get_infos.return_value = Accesspoints(accesspoints=[make_ap()])

    assert cli.main(["--dry-run"]) == 0

    nodes = json.loads(capsys.readouterr().out)
    assert list(nodes) == ["020000000010"]
    assert set(nodes["020000000010"]) == {"nodeinfo", "statistics", "neighbours"}
    assert nodes["020000000010"]["nodeinfo"]["hostname"] == "TestAP"


def test_dry_run_controller_error(backend, capsys):
    backend.get_infos.return_value = None

    assert cli.main(["--dry-run"]) == 1
    assert "Could not fetch" in capsys.readouterr().err


def test_sets_request_timeout(backend):
    with (
        patch.object(cli, "set_default_request_timeout") as set_timeout,
        patch.object(cli.ResponddClient, "start"),
    ):
        cli.main([])
    set_timeout.assert_called_once_with(30)


def test_without_dry_run_starts_client(backend):
    with patch.object(cli.ResponddClient, "start") as start:
        cli.main([])
    start.assert_called_once()


def test_dry_run_partial_failure(backend, capsys):
    backend.get_infos.side_effect = [Accesspoints(accesspoints=[make_ap()]), None]

    assert cli.main(["--dry-run"]) == 1

    out = capsys.readouterr()
    assert list(json.loads(out.out)) == ["020000000010"]
    assert "controllers: omada" in out.err
