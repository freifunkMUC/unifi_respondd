#!/usr/bin/env python3
"""Unit tests for unifi_respondd/vendors/omada.py module."""

from unittest.mock import Mock, patch

import pytest

from unifi_respondd.config import ControllerConfig
from unifi_respondd.vendors.omada import get_accesspoints, get_client_count_for_ap


def make_controller_cfg(**overrides):
    defaults = dict(
        type="omada",
        name="omada.lan",
        controller_url="https://omada.lan:8043",
        username="admin",
        password="password",
        ssid_regex=".*freifunk.*",
        offloader_mac={},
        ssl_verify=True,
    )
    defaults.update(overrides)
    return ControllerConfig(**defaults)


def make_more_ap_infos(**overrides):
    defaults = dict(
        ssidOverrides=[{"ssid": "freifunk-test", "ssidEnabled": True}],
        radioTraffic2g={"tx": 100, "rx": 200},
        radioTraffic5g={"tx": 300, "rx": 400},
        wp2g={"actualChannel": "6/2437MHz"},
        wp5g={"actualChannel": "36/5180MHz"},
        location=None,
        snmp={"location": "48.1351, 11.5820", "contact": "admin@example.com"},
        uptimeLong=86400,
    )
    defaults.update(overrides)
    return defaults


def make_ap(**overrides):
    defaults = dict(
        name="TestAP",
        mac="00-11-22-33-44-55",
        status=1,
        type="ap",
        showModel="EAP225",
        version="1.0.0",
    )
    defaults.update(overrides)
    return defaults


class TestGetClientCountForAp:
    """Test the get_client_count_for_ap function."""

    def test_no_clients(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        total, count24, count5 = get_client_count_for_ap([], cfg)
        assert total == 0
        assert count24 == 0
        assert count5 == 0

    def test_clients_mixed_bands(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        clients = [
            {"ssid": "freifunk-test", "channel": 6},
            {"ssid": "freifunk-test", "channel": 36},
            {"ssid": "other-network", "channel": 44},
        ]
        total, count24, count5 = get_client_count_for_ap(clients, cfg)
        assert total == 2
        assert count24 == 1
        assert count5 == 1


class TestGetAccesspoints:
    """Test the get_accesspoints function (main per-controller integration function)."""

    @patch("unifi_respondd.vendors.omada.Omada")
    def test_login_error_propagates(self, mock_omada_class):
        """A login failure now propagates -- the aggregator is responsible
        for catching it, not this function."""
        mock_omada_class.return_value.login.side_effect = Exception("login failed")

        with pytest.raises(Exception, match="login failed"):
            get_accesspoints(make_controller_cfg(), {"nodes": []}, "fallback_domain")

    @patch("unifi_respondd.vendors.omada.Omada")
    def test_basic_success_no_sites(self, mock_omada_class):
        instance = mock_omada_class.return_value
        instance.getCurrentUser.return_value = {"privilege": {"sites": []}}

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []

    @patch("unifi_respondd.vendors.omada.net.get_location_by_address")
    @patch("unifi_respondd.vendors.omada.Omada")
    def test_with_access_points(self, mock_omada_class, mock_get_location):
        instance = mock_omada_class.return_value
        instance.getCurrentUser.return_value = {
            "privilege": {"sites": [{"name": "site1"}]}
        }
        instance.getSiteDevices.return_value = [make_ap()]
        instance.getSiteAP.return_value = make_more_ap_infos()
        instance.getSiteClientsAP.return_value = []
        mock_get_location.return_value = (48.1351, 11.5820)

        ffnodes = {
            "nodes": [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "gateway": "10.0.0.1",
                    "gateway6": "fe80::1",
                    "domain": "ffmuc",
                }
            ]
        }
        cfg = make_controller_cfg(offloader_mac={"site1": "aa:bb:cc:dd:ee:ff"})

        result = get_accesspoints(cfg, ffnodes, "fallback_domain")

        assert len(result) == 1
        ap = result[0]
        assert ap.name == "TestAP"
        # MAC is normalized from dash-separated to colon-separated, lowercased.
        assert ap.mac == "00:11:22:33:44:55"
        assert ap.controller_type == "omada"
        assert ap.firmware_base == "Omada"
        assert ap.tx_bytes == 400  # 100 (2g) + 300 (5g)
        assert ap.rx_bytes == 600  # 200 (2g) + 400 (5g)
        assert {b.frequency for b in ap.wireless_bands} == {2437, 5180}
        assert ap.domain_code == "ffmuc"

    @patch("unifi_respondd.vendors.omada.net.get_location_by_address")
    @patch("unifi_respondd.vendors.omada.Omada")
    def test_ap_without_snmp_location_is_still_reported(
        self, mock_omada_class, mock_get_location
    ):
        """Regression test for a bugfix made during the multi-controller merge:
        an AP whose SNMP location is entirely unset (None, not just an empty
        string) used to be silently dropped from the output because the
        Accesspoint-building code lived nested inside the
        `if snmp.get("location") is not None:` branch. It must now be
        reported like any other AP that passes the SSID filter."""
        instance = mock_omada_class.return_value
        instance.getCurrentUser.return_value = {
            "privilege": {"sites": [{"name": "site1"}]}
        }
        instance.getSiteDevices.return_value = [make_ap()]
        instance.getSiteAP.return_value = make_more_ap_infos(
            snmp={"location": None, "contact": None}
        )
        instance.getSiteClientsAP.return_value = []

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )

        assert len(result) == 1
        assert result[0].name == "TestAP"
        assert result[0].snmp_location is None
        mock_get_location.assert_not_called()

    @patch("unifi_respondd.vendors.omada.Omada")
    def test_filters_non_ap_devices(self, mock_omada_class):
        instance = mock_omada_class.return_value
        instance.getCurrentUser.return_value = {
            "privilege": {"sites": [{"name": "site1"}]}
        }
        instance.getSiteDevices.return_value = [make_ap(type="switch")]

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []

    @patch("unifi_respondd.vendors.omada.Omada")
    def test_filters_aps_without_matching_ssid(self, mock_omada_class):
        instance = mock_omada_class.return_value
        instance.getCurrentUser.return_value = {
            "privilege": {"sites": [{"name": "site1"}]}
        }
        instance.getSiteDevices.return_value = [make_ap()]
        instance.getSiteAP.return_value = make_more_ap_infos(
            ssidOverrides=[{"ssid": "other-network", "ssidEnabled": True}]
        )

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
