#!/usr/bin/env python3
"""Unit tests for unified_respondd/config.py and backend selection."""

from unittest.mock import patch

import pytest
import yaml

from unified_respondd import backends, config
from unified_respondd.backends import unifi

UNIFI_CONFIG = {
    "controller_url": "unifi.example.org",
    "controller_port": 8443,
    "username": "user",
    "password": "secret",
    "ssid_regex": ".*freifunk.*",
    "offloader_mac": {},
    "nodelist": "https://map.example.org/meshviewer.json",
    "version": "v5",
    "ssl_verify": True,
    "multicast_enabled": False,
    "multicast_address": "ff05::2:1001",
    "multicast_port": 1001,
    "unicast_address": "fe80::1",
    "unicast_port": 10001,
    "interface": "eth0",
    "verbose": True,
}


class TestConfigFromDict:
    def test_defaults_to_unifi(self):
        cfg = config.Config.from_dict(UNIFI_CONFIG)
        assert cfg.backend == "unifi"
        assert isinstance(cfg.controller, unifi.ControllerConfig)
        assert cfg.controller.username == "user"
        assert cfg.interface == "eth0"

    def test_explicit_backend(self):
        cfg = config.Config.from_dict({**UNIFI_CONFIG, "backend": "unifi"})
        assert cfg.backend == "unifi"

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown backend 'foo'"):
            config.Config.from_dict({**UNIFI_CONFIG, "backend": "foo"})


class TestLoadBackend:
    def test_missing_dependency(self):
        error = ModuleNotFoundError("No module named 'pyunifi'", name="pyunifi")
        with patch("unified_respondd.backends.importlib.import_module") as imp:
            imp.side_effect = error
            with pytest.raises(ImportError, match=r"unified_respondd\[unifi\]"):
                backends.load("unifi")


class TestConfigFilePath:
    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch, tmp_path):
        for env in config.CONFIG_OS_ENVS:
            monkeypatch.delenv(env, raising=False)
        monkeypatch.chdir(tmp_path)

    def test_default_when_nothing_exists(self):
        assert config.config_file_path() == "./unified_respondd.yaml"

    def test_legacy_file(self, tmp_path):
        (tmp_path / "unifi_respondd.yaml").write_text("")
        assert config.config_file_path() == "./unifi_respondd.yaml"

    def test_new_file_wins_over_legacy(self, tmp_path):
        (tmp_path / "unifi_respondd.yaml").write_text("")
        (tmp_path / "unified_respondd.yaml").write_text("")
        assert config.config_file_path() == "./unified_respondd.yaml"

    def test_legacy_env(self, monkeypatch, tmp_path):
        (tmp_path / "unified_respondd.yaml").write_text("")
        monkeypatch.setenv("UNIFI_RESPONDD_CONFIG_FILE", "/etc/unifi.yaml")
        assert config.config_file_path() == "/etc/unifi.yaml"

    def test_new_env_wins(self, monkeypatch):
        monkeypatch.setenv("UNIFI_RESPONDD_CONFIG_FILE", "/etc/unifi.yaml")
        monkeypatch.setenv("UNIFIED_RESPONDD_CONFIG_FILE", "/etc/unified.yaml")
        assert config.config_file_path() == "/etc/unified.yaml"


class TestLoadConfig:
    def test_invalid_config_exits(self, capsys):
        with patch.object(config, "fetch_config_from_disk", return_value="foo: bar"):
            with pytest.raises(SystemExit) as e:
                config.load_config()
        assert e.value.code == 2
        assert capsys.readouterr().err == "Failed to lint file: 'controller_url'\n"

    def test_invalid_yaml_exits(self, capsys):
        with patch.object(config, "fetch_config_from_disk", return_value="foo: ["):
            with pytest.raises(SystemExit) as e:
                config.load_config()
        assert e.value.code == 1
        assert capsys.readouterr().err.startswith("Failed to load YAML file: ")

    def test_valid_config(self, tmp_path, monkeypatch):
        path = tmp_path / "cfg.yaml"
        path.write_text(yaml.safe_dump(UNIFI_CONFIG))
        monkeypatch.setenv("UNIFIED_RESPONDD_CONFIG_FILE", str(path))
        assert config.load_config()["username"] == "user"


class TestCredentialsNotInRepr:
    """Credentials must not end up in logs when a config is printed."""

    def test_unifi(self):
        cfg = config.Config.from_dict(UNIFI_CONFIG)
        assert "secret" not in repr(cfg)

    def test_omada(self):
        from unified_respondd.backends import omada

        cfg = omada.ControllerConfig.from_dict(
            {**UNIFI_CONFIG, "controller_url": "https://omada.example.org:8043"}
        )
        assert "secret" not in repr(cfg)

    def test_uisp(self):
        from unified_respondd.backends import uisp

        cfg = uisp.ControllerConfig.from_dict(
            {"controller_url": "https://uisp.example.org", "token": "secret"}
        )
        assert "secret" not in repr(cfg)
