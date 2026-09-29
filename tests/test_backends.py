#!/usr/bin/env python3
"""Every registered backend must implement the Backend protocol."""

import dataclasses
import inspect

import pytest

from unified_respondd import backends


@pytest.mark.parametrize("name", sorted(backends.BACKENDS))
def test_backend_implements_protocol(name):
    backend = backends.load(name)
    assert isinstance(backend, backends.Backend)
    assert dataclasses.is_dataclass(backend.ControllerConfig)
    assert inspect.ismethod(backend.ControllerConfig.from_dict)
    assert list(inspect.signature(backend.get_infos).parameters) == ["cfg"]


def test_protocol_rejects_incomplete_module():
    class NoGetInfos:
        ControllerConfig = object

    assert not isinstance(NoGetInfos(), backends.Backend)
