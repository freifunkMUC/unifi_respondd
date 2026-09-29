#!/usr/bin/env python3
"""The example configs must stay valid."""

import pathlib

import pytest
import yaml

from unified_respondd.config import Config

EXAMPLES = pathlib.Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize("backend", ["unifi", "omada", "uisp"])
def test_example_config(backend):
    cfg = Config.from_dict(yaml.safe_load((EXAMPLES / f"{backend}.yaml").read_text()))
    assert cfg.backend == backend
