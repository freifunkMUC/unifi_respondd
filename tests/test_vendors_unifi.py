#!/usr/bin/env python3
"""Unit tests for unifi_respondd/vendors/unifi.py module."""

from unittest.mock import Mock, patch

import pytest

from unifi_respondd.accesspoint import Accesspoint, WirelessBandInfo
from unifi_respondd.config import ControllerConfig
from unifi_respondd.vendors.unifi import (
    get_accesspoints,
    get_ap_channel_usage,
    get_client_count_for_ap,
)


def make_controller_cfg(**overrides):
    defaults = dict(
        type="unifi",
        name="unifi.lan",
        controller_url="unifi.lan",
        controller_port=8443,
        username="admin",
        password="password",
        ssid_regex=".*freifunk.*",
        offloader_mac={},
        version="v5",
        ssl_verify=True,
    )
    defaults.update(overrides)
    return ControllerConfig(**defaults)


class TestAccesspointDataclass:
    """Test the shared Accesspoint dataclass with UniFi-shaped data."""

    def test_accesspoint_creation(self):
        ap = Accesspoint(
            name="TestAP",
            mac="00:11:22:33:44:55",
            controller_type="unifi",
            controller_name="unifi.lan",
            firmware_base="UniFi",
            snmp_location="48.1351, 11.5820",
            latitude=48.1351,
            longitude=11.5820,
            contact="admin@example.com",
            model="UAP-AC-PRO",
            firmware="4.3.20.11298",
            uptime=86400,
            client_count=10,
            client_count24=5,
            client_count5=5,
            wireless_bands=[
                WirelessBandInfo(frequency=5180, rx_bytes=1000, tx_bytes=2000),
                WirelessBandInfo(frequency=2437, rx_bytes=500, tx_bytes=600),
            ],
            tx_bytes=2600,
            rx_bytes=1500,
            load_avg=0.5,
            mem_used=50000,
            mem_total=100000,
            mem_buffer=10000,
            gateway="10.0.0.1",
            gateway6="fe80::1",
            gateway_nexthop="aabbccddeeff",
            neighbour_macs=["aa:bb:cc:dd:ee:ff"],
            domain_code="ffmuc",
        )

        assert ap.name == "TestAP"
        assert ap.mac == "00:11:22:33:44:55"
        assert ap.client_count == 10
        assert ap.latitude == 48.1351
        assert ap.longitude == 11.5820
        assert ap.model == "UAP-AC-PRO"
        assert ap.domain_code == "ffmuc"
        assert len(ap.wireless_bands) == 2


class TestGetClientCountForAp:
    """Test the get_client_count_for_ap function."""

    def test_no_clients(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = []

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 0
        assert count24 == 0
        assert count5 == 0

    def test_clients_on_24ghz(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 6},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 11},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 2
        assert count24 == 2
        assert count5 == 0

    def test_clients_on_5ghz(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 36},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 44},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 2
        assert count24 == 0
        assert count5 == 2

    def test_clients_mixed_bands(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 6},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 36},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 11},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 3
        assert count24 == 2
        assert count5 == 1

    def test_clients_different_ap(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "freifunk-test", "ap_mac": "aa:bb:cc:dd:ee:ff", "channel": 6},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 36},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 1
        assert count24 == 0
        assert count5 == 1

    def test_clients_non_matching_ssid(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "other-network", "ap_mac": ap_mac, "channel": 6},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 36},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 1
        assert count24 == 0
        assert count5 == 1

    def test_clients_missing_essid(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"ap_mac": ap_mac, "channel": 6},
            {"essid": "freifunk-test", "ap_mac": ap_mac, "channel": 36},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 1
        assert count24 == 0
        assert count5 == 1

    def test_clients_case_insensitive_ssid(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = [
            {"essid": "FreiFunk-TEST", "ap_mac": ap_mac, "channel": 6},
            {"essid": "FREIFUNK-test", "ap_mac": ap_mac, "channel": 36},
        ]

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 2
        assert count24 == 1
        assert count5 == 1


class TestGetApChannelUsage:
    """Test the get_ap_channel_usage function."""

    def test_no_ssids(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = []

        result = get_ap_channel_usage(ssids, cfg)
        assert result == (None, None, None, None, None, None)

    def test_ssid_on_5ghz_only(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = [
            {
                "essid": "freifunk-test",
                "channel": 36,
                "rx_bytes": 1000,
                "tx_bytes": 2000,
            }
        ]

        channel5, rx5, tx5, channel24, rx24, tx24 = get_ap_channel_usage(ssids, cfg)
        assert channel5 == 36
        assert rx5 == 1000
        assert tx5 == 2000
        assert channel24 is None
        assert rx24 is None
        assert tx24 is None

    def test_ssid_on_24ghz_only(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = [
            {"essid": "freifunk-test", "channel": 6, "rx_bytes": 500, "tx_bytes": 600}
        ]

        channel5, rx5, tx5, channel24, rx24, tx24 = get_ap_channel_usage(ssids, cfg)
        assert channel5 is None
        assert rx5 is None
        assert tx5 is None
        assert channel24 == 6
        assert rx24 == 500
        assert tx24 == 600

    def test_ssid_on_both_bands(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = [
            {"essid": "freifunk-test", "channel": 6, "rx_bytes": 500, "tx_bytes": 600},
            {
                "essid": "freifunk-test",
                "channel": 36,
                "rx_bytes": 1000,
                "tx_bytes": 2000,
            },
        ]

        channel5, rx5, tx5, channel24, rx24, tx24 = get_ap_channel_usage(ssids, cfg)
        assert channel5 == 36
        assert rx5 == 1000
        assert tx5 == 2000
        assert channel24 == 6
        assert rx24 == 500
        assert tx24 == 600

    def test_ssid_non_matching(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = [
            {"essid": "other-network", "channel": 6, "rx_bytes": 500, "tx_bytes": 600},
            {
                "essid": "freifunk-test",
                "channel": 36,
                "rx_bytes": 1000,
                "tx_bytes": 2000,
            },
        ]

        channel5, rx5, tx5, channel24, rx24, tx24 = get_ap_channel_usage(ssids, cfg)
        assert channel5 == 36
        assert rx5 == 1000
        assert tx5 == 2000
        assert channel24 is None
        assert rx24 is None
        assert tx24 is None

    def test_ssid_missing_fields(self):
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = [{"essid": "freifunk-test"}]

        channel5, rx5, tx5, channel24, rx24, tx24 = get_ap_channel_usage(ssids, cfg)
        # When channel is missing, it defaults to 0 which is < 14, so treated as 2.4GHz
        assert channel5 is None
        assert rx5 is None
        assert tx5 is None
        assert channel24 == 0
        assert rx24 == 0
        assert tx24 == 0


class TestGetAccesspoints:
    """Test the get_accesspoints function (main per-controller integration function)."""

    @patch("unifi_respondd.vendors.unifi.Controller")
    @patch("unifi_respondd.vendors.unifi.Nominatim")
    def test_controller_error_propagates(self, mock_nominatim, mock_controller):
        """A connection failure now propagates -- the aggregator is responsible
        for catching it, not this function."""
        mock_controller.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            get_accesspoints(make_controller_cfg(), {"nodes": []}, "fallback_domain")

    @patch("unifi_respondd.vendors.unifi.Controller")
    @patch("unifi_respondd.vendors.unifi.Nominatim")
    def test_basic_success_no_sites(self, mock_nominatim, mock_controller):
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = []

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []

    @patch("unifi_respondd.vendors.unifi.Controller")
    @patch("unifi_respondd.vendors.unifi.Nominatim")
    @patch("unifi_respondd.vendors.unifi.get_client_count_for_ap")
    @patch("unifi_respondd.vendors.unifi.get_ap_channel_usage")
    @patch("unifi_respondd.net.get_location_by_address")
    def test_with_access_points(
        self,
        mock_get_location,
        mock_get_channel,
        mock_get_clients,
        mock_nominatim,
        mock_controller,
    ):
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

        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        mock_ap = {
            "name": "TestAP",
            "mac": "00:11:22:33:44:55",
            "state": 1,
            "type": "uap",
            "snmp_location": "48.1351, 11.5820",
            "snmp_contact": "admin@example.com",
            "model": "UAP-AC-PRO",
            "version": "4.3.20",
            "uptime": 86400,
            "sys_stats": {
                "loadavg_1": 0.5,
                "mem_used": 50000,
                "mem_buffer": 10000,
                "mem_total": 100000,
            },
            "vap_table": [
                {
                    "essid": "freifunk-test",
                    "channel": 36,
                    "rx_bytes": 1000,
                    "tx_bytes": 2000,
                }
            ],
        }

        mock_controller_instance.get_aps.return_value = [mock_ap]
        mock_controller_instance.get_clients.return_value = []

        mock_get_clients.return_value = (5, 2, 3)
        mock_get_channel.return_value = (36, 1000, 2000, None, None, None)
        mock_get_location.return_value = (48.1351, 11.5820)

        cfg = make_controller_cfg(offloader_mac={"testsite": "aa:bb:cc:dd:ee:ff"})
        result = get_accesspoints(cfg, ffnodes, "fallback_domain")

        assert len(result) == 1
        ap = result[0]
        assert ap.name == "TestAP"
        assert ap.mac == "00:11:22:33:44:55"
        assert ap.client_count == 5
        assert ap.controller_type == "unifi"
        assert ap.firmware_base == "UniFi"
        assert len(ap.wireless_bands) == 1
        assert ap.wireless_bands[0].frequency == 5180
        assert ap.domain_code == "ffmuc"

    @patch("unifi_respondd.vendors.unifi.Controller")
    @patch("unifi_respondd.vendors.unifi.Nominatim")
    def test_filters_non_uap_devices(self, mock_nominatim, mock_controller):
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        mock_ap = {
            "name": "TestSwitch",
            "mac": "00:11:22:33:44:55",
            "state": 1,
            "type": "usw",  # This is a switch, not an AP
        }

        mock_controller_instance.get_aps.return_value = [mock_ap]
        mock_controller_instance.get_clients.return_value = []

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []

    @patch("unifi_respondd.vendors.unifi.Controller")
    @patch("unifi_respondd.vendors.unifi.Nominatim")
    def test_filters_aps_without_matching_ssid(self, mock_nominatim, mock_controller):
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        mock_ap = {
            "name": "TestAP",
            "mac": "00:11:22:33:44:55",
            "state": 1,
            "type": "uap",
            "vap_table": [
                {
                    "essid": "other-network",  # Does not match freifunk regex
                    "channel": 36,
                    "rx_bytes": 1000,
                    "tx_bytes": 2000,
                }
            ],
        }

        mock_controller_instance.get_aps.return_value = [mock_ap]
        mock_controller_instance.get_clients.return_value = []

        result = get_accesspoints(
            make_controller_cfg(), {"nodes": []}, "fallback_domain"
        )
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
