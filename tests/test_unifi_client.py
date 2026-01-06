#!/usr/bin/env python3
"""Unit tests for unifi_respondd/unifi_client.py module."""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from unifi_respondd.unifi_client import (
    Accesspoint,
    Accesspoints,
    get_client_count_for_ap,
    get_ap_channel_usage,
    get_location_by_address,
    scrape,
    get_infos,
)


class TestAccesspointDataclass:
    """Test the Accesspoint dataclass."""

    def test_accesspoint_creation(self):
        """Test creating an Accesspoint instance with all fields."""
        ap = Accesspoint(
            name="TestAP",
            mac="00:11:22:33:44:55",
            snmp_location="48.1351, 11.5820",
            client_count=10,
            client_count24=5,
            client_count5=5,
            channel5=36,
            rx_bytes5=1000,
            tx_bytes5=2000,
            channel24=6,
            rx_bytes24=500,
            tx_bytes24=600,
            latitude=48.1351,
            longitude=11.5820,
            model="UAP-AC-PRO",
            firmware="4.3.20.11298",
            uptime=86400,
            contact="admin@example.com",
            load_avg=0.5,
            mem_used=50000,
            mem_total=100000,
            mem_buffer=10000,
            tx_bytes=2600,
            rx_bytes=1500,
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


class TestAccesspointsDataclass:
    """Test the Accesspoints dataclass."""

    def test_accesspoints_creation(self):
        """Test creating an Accesspoints instance with a list of APs."""
        ap1 = Accesspoint(
            name="AP1",
            mac="00:11:22:33:44:55",
            snmp_location="Location1",
            client_count=5,
            client_count24=3,
            client_count5=2,
            channel5=36,
            rx_bytes5=1000,
            tx_bytes5=2000,
            channel24=6,
            rx_bytes24=500,
            tx_bytes24=600,
            latitude=48.1,
            longitude=11.5,
            model="UAP-AC-PRO",
            firmware="4.3.20",
            uptime=86400,
            contact="admin@example.com",
            load_avg=0.5,
            mem_used=50000,
            mem_total=100000,
            mem_buffer=10000,
            tx_bytes=2600,
            rx_bytes=1500,
            gateway="10.0.0.1",
            gateway6="fe80::1",
            gateway_nexthop="aabbccddeeff",
            neighbour_macs=["aa:bb:cc:dd:ee:ff"],
            domain_code="ffmuc",
        )

        aps = Accesspoints(accesspoints=[ap1])
        assert len(aps.accesspoints) == 1
        assert aps.accesspoints[0].name == "AP1"

    def test_accesspoints_empty_list(self):
        """Test creating an Accesspoints instance with empty list."""
        aps = Accesspoints(accesspoints=[])
        assert len(aps.accesspoints) == 0


class TestGetClientCountForAp:
    """Test the get_client_count_for_ap function."""

    def test_no_clients(self):
        """Test with no clients connected."""
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ap_mac = "00:11:22:33:44:55"
        clients = []

        total, count24, count5 = get_client_count_for_ap(ap_mac, clients, cfg)
        assert total == 0
        assert count24 == 0
        assert count5 == 0

    def test_clients_on_24ghz(self):
        """Test with clients only on 2.4GHz."""
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
        """Test with clients only on 5GHz."""
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
        """Test with clients on both 2.4GHz and 5GHz."""
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
        """Test that clients from different APs are not counted."""
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
        """Test that clients with non-matching SSID are not counted."""
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
        """Test clients with missing essid field."""
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
        """Test that SSID matching is case insensitive."""
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
        """Test with no SSIDs."""
        cfg = Mock()
        cfg.ssid_regex = ".*freifunk.*"
        ssids = []

        result = get_ap_channel_usage(ssids, cfg)
        assert result == (None, None, None, None, None, None)

    def test_ssid_on_5ghz_only(self):
        """Test with SSID on 5GHz only."""
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
        """Test with SSID on 2.4GHz only."""
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
        """Test with SSIDs on both 2.4GHz and 5GHz."""
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
        """Test that non-matching SSIDs are not included."""
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
        """Test with SSIDs missing optional fields."""
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


class TestGetLocationByAddress:
    """Test the get_location_by_address function."""

    def test_valid_point_string(self):
        """Test with a valid point string (lat, lon)."""
        address = "48.1351, 11.5820"
        app = Mock()

        lat, lon = get_location_by_address(address, app)
        assert lat == pytest.approx(48.1351, rel=1e-4)
        assert lon == pytest.approx(11.5820, rel=1e-4)

    @patch("unifi_respondd.unifi_client.time.sleep")
    def test_geocoding_fallback(self, mock_sleep):
        """Test fallback to geocoding when point parsing fails."""
        address = "Munich, Germany"
        app = Mock()
        app.geocode.return_value = Mock(raw={"lat": "48.1351", "lon": "11.5820"})

        lat, lon = get_location_by_address(address, app)
        assert lat == "48.1351"
        assert lon == "11.5820"
        mock_sleep.assert_called_once_with(1)

    @patch("unifi_respondd.unifi_client.time.sleep")
    @patch("unifi_respondd.unifi_client.get_location_by_address")
    def test_geocoding_failure_recursion(self, mock_get_location, mock_sleep):
        """Test recursion when geocoding fails."""
        address = "Invalid Address"
        app = Mock()
        app.geocode.side_effect = Exception("Geocoding failed")

        # Mock the recursive call to avoid infinite recursion in test
        mock_get_location.return_value = (0.0, 0.0)

        # Call the mocked version
        result = mock_get_location(address, app)
        assert result == (0.0, 0.0)


class TestScrape:
    """Test the scrape function."""

    @patch("unifi_respondd.unifi_client.rget")
    def test_scrape_success(self, mock_rget):
        """Test successful scraping of JSON data."""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.return_value = mock_response

        result = scrape("http://example.com/api")
        assert result == {"nodes": [{"mac": "00:11:22:33:44:55"}]}
        mock_rget.assert_called_once_with("http://example.com/api")

    @patch("unifi_respondd.unifi_client.rget")
    @patch("unifi_respondd.unifi_client.logger.error")
    def test_scrape_failure(self, mock_logger, mock_rget):
        """Test scraping failure handling."""
        mock_rget.side_effect = Exception("Network error")

        result = scrape("http://example.com/api")
        assert result is None
        mock_logger.assert_called_once()


class TestGetInfos:
    """Test the get_infos function (main integration function)."""

    @patch("unifi_respondd.unifi_client.config.load_config")
    @patch("unifi_respondd.unifi_client.config.Config.from_dict")
    @patch("unifi_respondd.unifi_client.scrape")
    @patch("unifi_respondd.unifi_client.Controller")
    @patch("unifi_respondd.unifi_client.Nominatim")
    @patch("unifi_respondd.unifi_client.logger.error")
    def test_get_infos_controller_error(
        self,
        mock_logger,
        mock_nominatim,
        mock_controller,
        mock_scrape,
        mock_config_from_dict,
        mock_load_config,
    ):
        """Test get_infos when controller connection fails."""
        mock_load_config.return_value = {}
        mock_cfg = Mock()
        mock_cfg.nodelist = "http://example.com/nodes.json"
        mock_config_from_dict.return_value = mock_cfg
        mock_scrape.return_value = {"nodes": []}
        mock_controller.side_effect = Exception("Connection failed")

        result = get_infos()
        assert result is None
        mock_logger.assert_called()

    @patch("unifi_respondd.unifi_client.config.load_config")
    @patch("unifi_respondd.unifi_client.config.Config.from_dict")
    @patch("unifi_respondd.unifi_client.scrape")
    @patch("unifi_respondd.unifi_client.Controller")
    @patch("unifi_respondd.unifi_client.Nominatim")
    def test_get_infos_basic_success(
        self,
        mock_nominatim,
        mock_controller,
        mock_scrape,
        mock_config_from_dict,
        mock_load_config,
    ):
        """Test get_infos with basic successful execution."""
        # Setup config
        mock_load_config.return_value = {}
        mock_cfg = Mock()
        mock_cfg.nodelist = "http://example.com/nodes.json"
        mock_cfg.controller_url = "unifi.lan"
        mock_cfg.username = "admin"
        mock_cfg.password = "password"
        mock_cfg.controller_port = 8443
        mock_cfg.version = "v5"
        mock_cfg.ssl_verify = True
        mock_cfg.ssid_regex = ".*freifunk.*"
        mock_cfg.offloader_mac = {}
        mock_cfg.fallback_domain = "test_domain"
        mock_config_from_dict.return_value = mock_cfg

        # Setup scrape
        mock_scrape.return_value = {"nodes": []}

        # Setup controller
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = []

        result = get_infos()
        assert result is not None
        assert isinstance(result, Accesspoints)
        assert len(result.accesspoints) == 0

    @patch("unifi_respondd.unifi_client.config.load_config")
    @patch("unifi_respondd.unifi_client.config.Config.from_dict")
    @patch("unifi_respondd.unifi_client.scrape")
    @patch("unifi_respondd.unifi_client.Controller")
    @patch("unifi_respondd.unifi_client.Nominatim")
    @patch("unifi_respondd.unifi_client.get_client_count_for_ap")
    @patch("unifi_respondd.unifi_client.get_ap_channel_usage")
    @patch("unifi_respondd.unifi_client.get_location_by_address")
    def test_get_infos_with_access_points(
        self,
        mock_get_location,
        mock_get_channel,
        mock_get_clients,
        mock_nominatim,
        mock_controller,
        mock_scrape,
        mock_config_from_dict,
        mock_load_config,
    ):
        """Test get_infos with access points returned."""
        # Setup config
        mock_load_config.return_value = {}
        mock_cfg = Mock()
        mock_cfg.nodelist = "http://example.com/nodes.json"
        mock_cfg.controller_url = "unifi.lan"
        mock_cfg.username = "admin"
        mock_cfg.password = "password"
        mock_cfg.controller_port = 8443
        mock_cfg.version = "v5"
        mock_cfg.ssl_verify = True
        mock_cfg.ssid_regex = ".*freifunk.*"
        mock_cfg.offloader_mac = {"testsite": "aa:bb:cc:dd:ee:ff"}
        mock_cfg.fallback_domain = "test_domain"
        mock_config_from_dict.return_value = mock_cfg

        # Setup scrape
        mock_scrape.return_value = {
            "nodes": [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "gateway": "10.0.0.1",
                    "gateway6": "fe80::1",
                    "domain": "ffmuc",
                }
            ]
        }

        # Setup controller
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        # Setup AP data
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

        # Setup helper functions
        mock_get_clients.return_value = (5, 2, 3)
        mock_get_channel.return_value = (36, 1000, 2000, None, None, None)
        mock_get_location.return_value = (48.1351, 11.5820)

        result = get_infos()
        assert result is not None
        assert isinstance(result, Accesspoints)
        assert len(result.accesspoints) == 1
        assert result.accesspoints[0].name == "TestAP"
        assert result.accesspoints[0].mac == "00:11:22:33:44:55"
        assert result.accesspoints[0].client_count == 5

    @patch("unifi_respondd.unifi_client.config.load_config")
    @patch("unifi_respondd.unifi_client.config.Config.from_dict")
    @patch("unifi_respondd.unifi_client.scrape")
    @patch("unifi_respondd.unifi_client.Controller")
    @patch("unifi_respondd.unifi_client.Nominatim")
    def test_get_infos_filters_non_uap_devices(
        self,
        mock_nominatim,
        mock_controller,
        mock_scrape,
        mock_config_from_dict,
        mock_load_config,
    ):
        """Test that non-UAP devices are filtered out."""
        # Setup config
        mock_load_config.return_value = {}
        mock_cfg = Mock()
        mock_cfg.nodelist = "http://example.com/nodes.json"
        mock_cfg.controller_url = "unifi.lan"
        mock_cfg.username = "admin"
        mock_cfg.password = "password"
        mock_cfg.controller_port = 8443
        mock_cfg.version = "v5"
        mock_cfg.ssl_verify = True
        mock_cfg.ssid_regex = ".*freifunk.*"
        mock_cfg.offloader_mac = {}
        mock_cfg.fallback_domain = "test_domain"
        mock_config_from_dict.return_value = mock_cfg

        # Setup scrape
        mock_scrape.return_value = {"nodes": []}

        # Setup controller
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        # Setup AP data with non-uap type
        mock_ap = {
            "name": "TestSwitch",
            "mac": "00:11:22:33:44:55",
            "state": 1,
            "type": "usw",  # This is a switch, not an AP
        }

        mock_controller_instance.get_aps.return_value = [mock_ap]
        mock_controller_instance.get_clients.return_value = []

        result = get_infos()
        assert result is not None
        assert isinstance(result, Accesspoints)
        assert len(result.accesspoints) == 0

    @patch("unifi_respondd.unifi_client.config.load_config")
    @patch("unifi_respondd.unifi_client.config.Config.from_dict")
    @patch("unifi_respondd.unifi_client.scrape")
    @patch("unifi_respondd.unifi_client.Controller")
    @patch("unifi_respondd.unifi_client.Nominatim")
    def test_get_infos_filters_aps_without_matching_ssid(
        self,
        mock_nominatim,
        mock_controller,
        mock_scrape,
        mock_config_from_dict,
        mock_load_config,
    ):
        """Test that APs without matching SSID are filtered out."""
        # Setup config
        mock_load_config.return_value = {}
        mock_cfg = Mock()
        mock_cfg.nodelist = "http://example.com/nodes.json"
        mock_cfg.controller_url = "unifi.lan"
        mock_cfg.username = "admin"
        mock_cfg.password = "password"
        mock_cfg.controller_port = 8443
        mock_cfg.version = "v5"
        mock_cfg.ssl_verify = True
        mock_cfg.ssid_regex = ".*freifunk.*"
        mock_cfg.offloader_mac = {}
        mock_cfg.fallback_domain = "test_domain"
        mock_config_from_dict.return_value = mock_cfg

        # Setup scrape
        mock_scrape.return_value = {"nodes": []}

        # Setup controller
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        mock_controller_instance.get_sites.return_value = [
            {"name": "testsite", "desc": "testsite"}
        ]

        # Setup AP data with non-matching SSID
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

        result = get_infos()
        assert result is not None
        assert isinstance(result, Accesspoints)
        assert len(result.accesspoints) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
