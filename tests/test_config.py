#!/usr/bin/env python3
"""Unit tests for unified_respondd/config.py and backend selection."""

import subprocess
import sys
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
        [controller] = cfg.controllers
        assert controller.name == "unifi"
        assert controller.backend == "unifi"
        assert isinstance(controller.config, unifi.ControllerConfig)
        assert controller.config.username == "user"
        assert cfg.interface == "eth0"

    def test_explicit_backend(self):
        cfg = config.Config.from_dict({**UNIFI_CONFIG, "backend": "unifi"})
        assert cfg.controllers[0].backend == "unifi"

    def test_unknown_location_default(self):
        cfg = config.Config.from_dict(UNIFI_CONFIG)
        assert cfg.controllers[0].unknown_location == "report"

    @pytest.mark.parametrize("mode", ["report", "omit", "skip"])
    def test_unknown_location(self, mode):
        cfg = config.Config.from_dict({**UNIFI_CONFIG, "unknown_location": mode})
        assert cfg.controllers[0].unknown_location == mode

    def test_invalid_unknown_location(self):
        with pytest.raises(ValueError, match="Invalid unknown_location 'hide'"):
            config.Config.from_dict({**UNIFI_CONFIG, "unknown_location": "hide"})

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown backend 'foo'"):
            config.Config.from_dict({**UNIFI_CONFIG, "backend": "foo"})


RESPONDD_CONFIG = {
    k: UNIFI_CONFIG[k]
    for k in (
        "multicast_enabled",
        "multicast_address",
        "multicast_port",
        "unicast_address",
        "unicast_port",
        "interface",
        "verbose",
    )
}
UNIFI_CONTROLLER = {k: v for k, v in UNIFI_CONFIG.items() if k not in RESPONDD_CONFIG}
UISP_CONTROLLER = {
    "backend": "uisp",
    "controller_url": "https://uisp.lan",
    "token": "t",
}


class TestControllers:
    def test_list(self):
        cfg = config.Config.from_dict(
            {**RESPONDD_CONFIG, "controllers": [UNIFI_CONTROLLER, UISP_CONTROLLER]}
        )
        assert [c.backend for c in cfg.controllers] == ["unifi", "uisp"]
        assert [c.name for c in cfg.controllers] == ["unifi1", "uisp2"]
        assert cfg.controllers[1].config.token == "t"

    def test_name(self):
        cfg = config.Config.from_dict(
            {**RESPONDD_CONFIG, "controllers": [{**UISP_CONTROLLER, "name": "links"}]}
        )
        assert cfg.controllers[0].name == "links"

    def test_unknown_location_default_and_override(self):
        cfg = config.Config.from_dict(
            {
                **RESPONDD_CONFIG,
                "unknown_location": "omit",
                "controllers": [
                    UNIFI_CONTROLLER,
                    {**UISP_CONTROLLER, "unknown_location": "skip"},
                ],
            }
        )
        assert [c.unknown_location for c in cfg.controllers] == ["omit", "skip"]

    def test_invalid_unknown_location_of_controller(self):
        with pytest.raises(ValueError, match="Invalid unknown_location"):
            config.Config.from_dict(
                {
                    **RESPONDD_CONFIG,
                    "controllers": [{**UISP_CONTROLLER, "unknown_location": "hide"}],
                }
            )

    @pytest.mark.parametrize("controllers", [[], None, {"backend": "uisp"}])
    def test_invalid_list(self, controllers):
        with pytest.raises(ValueError, match="non-empty list"):
            config.Config.from_dict({**RESPONDD_CONFIG, "controllers": controllers})

    def test_missing_key_of_controller(self):
        with pytest.raises(KeyError, match="token"):
            config.Config.from_dict(
                {
                    **RESPONDD_CONFIG,
                    "controllers": [{"backend": "uisp", "controller_url": "x"}],
                }
            )

    def test_yaml_anchors_share_keys(self):
        cfg = config.Config.from_dict(
            yaml.safe_load(
                """
defaults: &unifi
  backend: unifi
  controller_port: 8443
  username: user
  password: secret
  ssid_regex: .*freifunk.*
  offloader_mac: {}
  nodelist: https://map.example.org/meshviewer.json
  version: v5
  ssl_verify: true
controllers:
  - <<: *unifi
    controller_url: unifi1.example.org
  - <<: *unifi
    controller_url: unifi2.example.org
multicast_enabled: false
multicast_address: ff05::2:1001
multicast_port: 1001
unicast_address: fe80::1
unicast_port: 10001
interface: eth0
verbose: false
"""
            )
        )
        assert [c.config.controller_url for c in cfg.controllers] == [
            "unifi1.example.org",
            "unifi2.example.org",
        ]


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


@pytest.mark.parametrize(
    "backend,missing",
    [("uisp", ["geopy", "pyunifi"]), ("omada", ["pyunifi"])],
)
def test_backend_imports_only_its_extra(backend, missing):
    """A backend must work with only the dependencies of its extra installed."""
    code = (
        "import sys\n"
        f"sys.modules.update(dict.fromkeys({missing!r}))\n"
        f"import unified_respondd.backends.{backend}\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
