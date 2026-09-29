#!/usr/bin/env python3
"""The example configs must stay valid."""

import pathlib

import pytest
import yaml

from unified_respondd.config import Config

EXAMPLES = pathlib.Path(__file__).parent.parent / "examples"


def load(name):
    return Config.from_dict(yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text()))


@pytest.mark.parametrize("backend", ["unifi", "omada", "uisp"])
def test_example_config(backend):
    assert [controller.backend for controller in load(backend).controllers] == [backend]


def test_multi_example_config():
    controllers = load("multi").controllers
    assert [(c.name, c.backend) for c in controllers] == [
        ("unifi", "unifi"),
        ("omada", "omada"),
        ("uisp", "uisp"),
    ]
    assert [c.unknown_location for c in controllers] == ["report", "omit", "report"]
    assert controllers[1].config.nodelist == "https://MAPURL/data/meshviewer.json"
