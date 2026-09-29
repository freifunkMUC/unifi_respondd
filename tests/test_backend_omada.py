#!/usr/bin/env python3
"""Unit tests for unified_respondd/backends/omada.py module."""

import copy
from unittest.mock import Mock, patch

import pytest

from unified_respondd.backends import omada
from unified_respondd.backends.omada import (
    ControllerConfig,
    _extract_loadavg,
    _extract_memory,
    get_ap_frequency,
    get_client_count_for_ap,
    get_infos,
)
from unified_respondd.model import Radio

OMADA_CONFIG = {
    "controller_url": "https://omada.example.org:8043",
    "username": "user",
    "password": "secret",
    "ssid_regex": ".*freifunk.*",
    "offloader_mac": {"Site A": "02:00:00:00:00:01"},
    "nodelist": "https://map.example.org/meshviewer.json",
    "ssl_verify": True,
}

NODES = {
    "nodes": [
        {
            "mac": "02:00:00:00:00:01",
            "gateway": "02:00:00:00:00:aa",
            "gateway6": "02:00:00:00:00:bb",
            "domain": "ffmuc_test",
        }
    ]
}

FREIFUNK = [{"ssid": "freifunk", "ssidEnabled": True}]

DEVICES = {
    "Site A": [
        {
            "name": "ap1",
            "mac": "02-00-00-00-00-10",
            "status": 14,
            "type": "ap",
            "showModel": "EAP245",
            "version": "5.1.0",
            "uplink": "02-00-00-00-00-99",
        },
        {"name": "offline", "mac": "02-00-00-00-00-11", "status": 0, "type": "ap"},
        {"name": "pending", "mac": "02-00-00-00-00-12", "status": 20, "type": "ap"},
        {"name": "switch", "mac": "02-00-00-00-00-13", "status": 14, "type": "switch"},
    ],
    "Site B": [
        {
            "name": "private",
            "mac": "02-00-00-00-00-14",
            "status": 14,
            "type": "ap",
            "showModel": "EAP110",
            "version": "4.0",
        },
    ],
}

DETAILS = {
    "02-00-00-00-00-10": {
        "ssidOverrides": FREIFUNK + [{"ssid": "private", "ssidEnabled": True}],
        "uptimeLong": 1000,
        "cpuUtil": 25,
        "memUtil": 40,
        "radioTraffic2g": {"tx": 1, "rx": 2},
        "radioTraffic5g": {"tx": 10, "rx": 20},
        "wp2g": {"actualChannel": "6 / 2437MHz"},
        "wp5g": {"actualChannel": "36 / 5180MHz"},
        "snmp": {"location": "48.1, 11.5", "contact": "noc@example.org"},
    },
    "02-00-00-00-00-14": {
        "ssidOverrides": [{"ssid": "private", "ssidEnabled": True}],
        "snmp": {"location": "48.1, 11.5"},
    },
}

CLIENTS = {
    "02-00-00-00-00-10": [
        {"ssid": "freifunk", "channel": 36},
        {"ssid": "freifunk", "channel": 6},
        {"ssid": "private", "channel": 6},
    ]
}


class FakeOmada:
    """A minimal stand-in for the Omada API with synthetic data."""

    instances = []

    def __init__(self, baseurl=None, site="Default", verify=True, verbose=False):
        self.devices = copy.deepcopy(DEVICES)
        self.details = copy.deepcopy(DETAILS)
        self.logins = 0
        self.logged_out = False
        FakeOmada.instances.append(self)

    def login(self, username=None, password=None):
        self.logins += 1

    def logout(self):
        self.logged_out = True

    def getCurrentUser(self):
        return {"privilege": {"sites": [{"name": "Site A"}, {"name": "Site B"}]}}

    def getSiteDevices(self, site=None):
        return self.devices[site]

    def getSiteAP(self, site=None, mac=None):
        return self.details[mac]

    def getSiteClientsAP(self, site=None, apmac=None):
        return iter(CLIENTS.get(apmac, []))


@pytest.fixture
def cfg():
    return ControllerConfig.from_dict(OMADA_CONFIG)


@pytest.fixture
def fake_omada():
    FakeOmada.instances = []
    with (
        patch.object(omada, "Omada", FakeOmada),
        patch.object(omada, "scrape", return_value=NODES),
        patch.object(omada, "Nominatim"),
    ):
        yield FakeOmada


class TestControllerConfig:
    def test_from_dict(self):
        cfg = ControllerConfig.from_dict(OMADA_CONFIG)
        assert cfg.controller_url == "https://omada.example.org:8043"
        assert cfg.fallback_domain == "omada_respondd_fallback"

    def test_legacy_keys_are_ignored(self):
        cfg = ControllerConfig.from_dict({**OMADA_CONFIG, "controller_port": 8043})
        assert cfg.username == "user"


class TestHelpers:
    @pytest.mark.parametrize(
        "channel,frequency",
        [("6 / 2437MHz", 2437), ("36 / 5180MHz", 5180), ("N/A", None), ("x", None)],
    )
    def test_get_ap_frequency(self, channel, frequency):
        assert get_ap_frequency(channel) == frequency

    def test_client_count(self, cfg):
        assert get_client_count_for_ap(CLIENTS["02-00-00-00-00-10"], cfg) == (2, 1, 1)

    def test_loadavg_from_sys_stats(self):
        assert _extract_loadavg({"sys_stats": {"loadavg_1": "0,5"}}, {}) == 0.5

    def test_loadavg_from_cpu_util(self):
        assert _extract_loadavg({}, {"cpuUtil": 25}) == 0.25

    def test_memory_from_sys_stats(self):
        ap = {"sys_stats": {"mem_used": 300, "mem_buffer": 20, "mem_total": 600000}}
        assert _extract_memory(ap, {}) == (300, 20, 600000)

    def test_memory_from_util(self):
        assert _extract_memory({}, {"memUtil": 40}) == (40960, 0, 102400)

    def test_memory_without_values(self):
        assert _extract_memory({}, {}) == (0, 0, 102400)

    def test_memory_total_is_clamped(self):
        """Avoid a total of 0 kB, meshviewer would divide by zero."""
        ap = {"sys_stats": {"mem_used": 800, "mem_total": 500}}
        assert _extract_memory(ap, {}) == (800, 0, 1024)


class TestGetInfos:
    def test_login_error(self, cfg, fake_omada):
        with patch.object(FakeOmada, "login", side_effect=Exception("denied")):
            assert get_infos(cfg) is None

    def test_accesspoint(self, cfg, fake_omada):
        aps = get_infos(cfg).accesspoints
        assert [ap.name for ap in aps] == ["ap1"]
        ap = aps[0]
        assert ap.mac == "02:00:00:00:00:10"
        assert ap.firmware_base == "Omada"
        assert ap.model == "EAP245"
        assert (ap.latitude, ap.longitude) == (48.1, 11.5)
        assert ap.contact == "noc@example.org"
        assert (ap.client_count, ap.client_count24, ap.client_count5) == (2, 1, 1)
        assert (ap.tx_bytes, ap.rx_bytes) == (11, 22)
        assert ap.load_avg == 0.25
        assert ap.radios == [Radio(frequency=2437), Radio(frequency=5180)]
        assert ap.gateway == "02:00:00:00:00:aa"
        assert ap.gateway_nexthop == "020000000001"
        assert ap.domain_code == "ffmuc_test"
        assert ap.neighbour_macs == ["02:00:00:00:00:01", "02:00:00:00:00:99"]

    @pytest.mark.parametrize("enabled", [{"ssidEnabled": False}, {}])
    def test_skip_ap_with_disabled_ssid(self, cfg, fake_omada, enabled):
        details = {
            **DETAILS["02-00-00-00-00-10"],
            "ssidOverrides": [{"ssid": "freifunk", **enabled}],
        }
        with patch.dict(DETAILS, {"02-00-00-00-00-10": details}):
            assert get_infos(cfg).accesspoints == []

    def test_native_location_without_snmp_location(self, cfg, fake_omada):
        details = DETAILS["02-00-00-00-00-10"]
        details = {
            **details,
            "location": {"latitude": 48.2, "longitude": 11.6},
            "snmp": {"location": ""},
        }
        with patch.dict(DETAILS, {"02-00-00-00-00-10": details}):
            ap = get_infos(cfg).accesspoints[0]
        assert (ap.latitude, ap.longitude) == (48.2, 11.6)

    @pytest.mark.parametrize("snmp", [{}, {"snmp": None}, {"snmp": {}}])
    def test_ap_without_snmp_location(self, cfg, fake_omada, snmp):
        details = {**DETAILS["02-00-00-00-00-10"], "location": None}
        del details["snmp"]
        details.update(snmp)
        with patch.dict(DETAILS, {"02-00-00-00-00-10": details}):
            aps = get_infos(cfg).accesspoints
        assert [ap.name for ap in aps] == ["ap1"]
        assert (aps[0].latitude, aps[0].longitude) == (0.0, 0.0)
        assert aps[0].contact is None

    def test_fallback_domain_without_offloader(self, cfg, fake_omada):
        cfg.offloader_mac = {}
        cfg.fallback_domain = "fallback"
        ap = get_infos(cfg).accesspoints[0]
        assert ap.domain_code == "fallback"
        assert ap.gateway is None
        assert ap.neighbour_macs == [None, "02:00:00:00:00:99"]

    def test_one_session_for_all_sites(self, cfg, fake_omada):
        get_infos(cfg)
        assert len(FakeOmada.instances) == 1
        assert FakeOmada.instances[0].logins == 1

    def test_logout(self, cfg, fake_omada):
        get_infos(cfg)
        assert FakeOmada.instances[0].logged_out

    def test_logout_on_error(self, cfg, fake_omada):
        with patch.object(FakeOmada, "getCurrentUser", side_effect=Exception("boom")):
            with pytest.raises(Exception, match="boom"):
                get_infos(cfg)
        assert FakeOmada.instances[0].logged_out

    def test_logout_error_is_logged(self, cfg, fake_omada):
        with (
            patch.object(FakeOmada, "logout", side_effect=Exception("gone")),
            patch.object(omada.logger, "error") as error,
        ):
            assert len(get_infos(cfg).accesspoints) == 1
        error.assert_called_once()


class TestConfigIntegration:
    def test_backend_selection(self):
        from unified_respondd.config import Config

        cfg = Config.from_dict(
            {
                **OMADA_CONFIG,
                "backend": "omada",
                "multicast_enabled": False,
                "multicast_address": "ff05::2:1001",
                "multicast_port": 1001,
                "unicast_address": "fe80::1",
                "unicast_port": 10001,
                "interface": "eth0",
                "verbose": False,
            }
        )
        assert isinstance(cfg.controller, ControllerConfig)


def test_main_prints_infos(capsys):
    with (
        patch("unified_respondd.config.load_config", return_value={}),
        patch("unified_respondd.config.Config.from_dict", return_value=Mock()),
        patch.object(omada, "get_infos", return_value="infos"),
    ):
        omada.main()
    assert capsys.readouterr().out == "infos\n"
