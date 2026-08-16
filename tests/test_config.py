#!/usr/bin/env python3
"""Unit tests for unifi_respondd/config.py module."""

import pytest

from unifi_respondd.config import Config, ControllerConfig

LEGACY_FLAT_CONFIG = {
    "controller_url": "unifi.lan",
    "controller_port": 8443,
    "username": "ubnt",
    "password": "ubnt",
    "ssid_regex": ".*freifunk.*",
    "offloader_mac": {"SiteName": "00:00:00:00:00:00"},
    "nodelist": "https://example.com/data/meshviewer.json",
    "version": "v5",
    "ssl_verify": True,
    "multicast_enabled": False,
    "multicast_address": "ff05::2:1001",
    "multicast_port": 1001,
    "unicast_address": "fe80::68ff:94ff:fe00:1504",
    "unicast_port": 10001,
    "interface": "eth0",
    "verbose": True,
}

MULTI_CONTROLLER_CONFIG = {
    "controllers": [
        {
            "type": "unifi",
            "name": "unifi-site-a",
            "controller_url": "unifi-a.lan",
            "controller_port": 8443,
            "username": "ubnt",
            "password": "ubnt",
            "ssid_regex": ".*freifunk.*",
            "offloader_mac": {"SiteNameA": "00:00:00:00:00:00"},
            "version": "v5",
            "ssl_verify": True,
        },
        {
            "type": "omada",
            "name": "omada-site-c",
            "controller_url": "https://omada.lan:8043",
            "username": "omada",
            "password": "omada",
            "ssid_regex": ".*freifunk.*",
            "offloader_mac": {"SiteNameC": "22:22:22:22:22:22"},
            "ssl_verify": True,
        },
    ],
    "nodelist": "https://example.com/data/meshviewer.json",
    "fallback_domain": "unifi_respondd_fallback",
    "multicast_enabled": False,
    "multicast_address": "ff05::2:1001",
    "multicast_port": 1001,
    "unicast_address": "fe80::68ff:94ff:fe00:1504",
    "unicast_port": 10001,
    "interface": "eth0",
    "verbose": True,
}


class TestControllerConfigFromDict:
    """Test ControllerConfig.from_dict."""

    def test_name_defaults_to_controller_url(self):
        cfg = ControllerConfig.from_dict(
            {
                "type": "unifi",
                "controller_url": "unifi.lan",
                "username": "ubnt",
                "password": "ubnt",
                "ssid_regex": ".*freifunk.*",
                "offloader_mac": {},
            }
        )
        assert cfg.name == "unifi.lan"

    def test_explicit_name_is_kept(self):
        cfg = ControllerConfig.from_dict(
            {
                "type": "omada",
                "name": "my-omada",
                "controller_url": "https://omada.lan",
                "username": "omada",
                "password": "omada",
                "ssid_regex": ".*freifunk.*",
                "offloader_mac": {},
            }
        )
        assert cfg.name == "my-omada"

    def test_controller_port_defaults_to_none(self):
        cfg = ControllerConfig.from_dict(
            {
                "type": "omada",
                "controller_url": "https://omada.lan",
                "username": "omada",
                "password": "omada",
                "ssid_regex": ".*freifunk.*",
                "offloader_mac": {},
            }
        )
        assert cfg.controller_port is None

    def test_missing_required_key_raises(self):
        with pytest.raises(KeyError):
            ControllerConfig.from_dict(
                {
                    "type": "unifi",
                    "controller_url": "unifi.lan",
                    # missing username/password/ssid_regex/offloader_mac
                }
            )


class TestConfigFromDictLegacyFlat:
    """Test Config.from_dict with the legacy flat (pre-multi-controller) shape."""

    def test_synthesizes_single_unifi_controller(self):
        cfg = Config.from_dict(LEGACY_FLAT_CONFIG)
        assert len(cfg.controllers) == 1
        controller = cfg.controllers[0]
        assert controller.type == "unifi"
        assert controller.name == "unifi.lan"
        assert controller.controller_url == "unifi.lan"
        assert controller.controller_port == 8443
        assert controller.username == "ubnt"
        assert controller.password == "ubnt"
        assert controller.ssid_regex == ".*freifunk.*"
        assert controller.offloader_mac == {"SiteName": "00:00:00:00:00:00"}
        assert controller.version == "v5"
        assert controller.ssl_verify is True

    def test_shared_fields_are_parsed(self):
        cfg = Config.from_dict(LEGACY_FLAT_CONFIG)
        assert cfg.nodelist == "https://example.com/data/meshviewer.json"
        assert cfg.interface == "eth0"
        assert cfg.multicast_enabled is False
        assert cfg.verbose is True

    def test_missing_required_key_raises(self):
        broken = dict(LEGACY_FLAT_CONFIG)
        del broken["username"]
        with pytest.raises(KeyError):
            Config.from_dict(broken)

    def test_fallback_domain_defaults(self):
        flat = dict(LEGACY_FLAT_CONFIG)
        cfg = Config.from_dict(flat)
        assert cfg.fallback_domain == "unifi_respondd_fallback"


class TestConfigFromDictMultiController:
    """Test Config.from_dict with the new nested controllers: shape."""

    def test_parses_mixed_vendor_controllers(self):
        cfg = Config.from_dict(MULTI_CONTROLLER_CONFIG)
        assert len(cfg.controllers) == 2
        assert cfg.controllers[0].type == "unifi"
        assert cfg.controllers[0].name == "unifi-site-a"
        assert cfg.controllers[1].type == "omada"
        assert cfg.controllers[1].name == "omada-site-c"
        assert cfg.controllers[1].controller_port is None

    def test_shared_fields_are_parsed(self):
        cfg = Config.from_dict(MULTI_CONTROLLER_CONFIG)
        assert cfg.nodelist == "https://example.com/data/meshviewer.json"
        assert cfg.fallback_domain == "unifi_respondd_fallback"

    def test_missing_required_key_in_one_controller_raises(self):
        broken = {
            "controllers": [
                {
                    "type": "unifi",
                    "controller_url": "unifi.lan",
                    # missing username/password/ssid_regex/offloader_mac
                }
            ],
            "nodelist": "https://example.com/data/meshviewer.json",
            "multicast_enabled": False,
            "multicast_address": "ff05::2:1001",
            "multicast_port": 1001,
            "unicast_address": "fe80::68ff:94ff:fe00:1504",
            "unicast_port": 10001,
            "interface": "eth0",
            "verbose": True,
        }
        with pytest.raises(KeyError):
            Config.from_dict(broken)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
