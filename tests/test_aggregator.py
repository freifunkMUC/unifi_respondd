#!/usr/bin/env python3
"""Unit tests for unifi_respondd/aggregator.py module."""

from unittest.mock import Mock, patch

import pytest

from unifi_respondd.accesspoint import Accesspoint
from unifi_respondd.aggregator import get_infos
from unifi_respondd.config import Config, ControllerConfig


def make_ap(name, controller_name):
    return Accesspoint(
        name=name,
        mac="00:11:22:33:44:55",
        controller_type="unifi",
        controller_name=controller_name,
        firmware_base="UniFi",
        snmp_location=None,
        latitude=0.0,
        longitude=0.0,
        contact=None,
        model="model",
        firmware="1.0",
        uptime=1,
        client_count=0,
        client_count24=0,
        client_count5=0,
        wireless_bands=[],
        tx_bytes=0,
        rx_bytes=0,
        load_avg=0.0,
        mem_used=0,
        mem_total=0,
        mem_buffer=0,
        gateway=None,
        gateway6=None,
        gateway_nexthop=None,
        neighbour_macs=[],
        domain_code="ffmuc",
    )


def make_config(controllers):
    return Config(
        controllers=controllers,
        nodelist="https://example.com/meshviewer.json",
        fallback_domain="fallback",
        multicast_address="ff05::2:1001",
        multicast_port=1001,
        unicast_address="fe80::1",
        unicast_port=10001,
        interface="eth0",
        verbose=False,
        multicast_enabled=False,
    )


def make_controller_cfg(type_, name):
    return ControllerConfig(
        type=type_,
        name=name,
        controller_url=f"{name}.lan",
        username="user",
        password="pass",
        ssid_regex=".*freifunk.*",
        offloader_mac={},
    )


class TestGetInfos:
    @patch("unifi_respondd.aggregator.net.scrape")
    def test_aggregates_mixed_vendors(self, mock_scrape):
        mock_scrape.return_value = {"nodes": []}
        cfg = make_config(
            [
                make_controller_cfg("unifi", "unifi-a"),
                make_controller_cfg("omada", "omada-b"),
            ]
        )

        with patch.dict(
            "unifi_respondd.aggregator.VENDOR_CLIENTS",
            {
                "unifi": Mock(return_value=[make_ap("ap1", "unifi-a")]),
                "omada": Mock(return_value=[make_ap("ap2", "omada-b")]),
            },
        ):
            result = get_infos(cfg)

        assert [ap.name for ap in result] == ["ap1", "ap2"]

    @patch("unifi_respondd.aggregator.net.scrape")
    def test_one_controller_failing_does_not_block_others(self, mock_scrape):
        mock_scrape.return_value = {"nodes": []}
        cfg = make_config(
            [
                make_controller_cfg("unifi", "broken"),
                make_controller_cfg("omada", "healthy"),
            ]
        )

        def raise_error(*args, **kwargs):
            raise Exception("connection refused")

        with patch.dict(
            "unifi_respondd.aggregator.VENDOR_CLIENTS",
            {
                "unifi": Mock(side_effect=raise_error),
                "omada": Mock(return_value=[make_ap("ap2", "healthy")]),
            },
        ), patch("unifi_respondd.aggregator.logger.error") as mock_log_error:
            result = get_infos(cfg)

        assert [ap.name for ap in result] == ["ap2"]
        mock_log_error.assert_called_once()
        assert "broken" in mock_log_error.call_args[0][0]

    @patch("unifi_respondd.aggregator.net.scrape")
    def test_unknown_controller_type_is_skipped(self, mock_scrape):
        mock_scrape.return_value = {"nodes": []}
        cfg = make_config(
            [
                make_controller_cfg("does-not-exist", "mystery"),
                make_controller_cfg("omada", "healthy"),
            ]
        )

        with patch.dict(
            "unifi_respondd.aggregator.VENDOR_CLIENTS",
            {"omada": Mock(return_value=[make_ap("ap2", "healthy")])},
            clear=True,
        ), patch("unifi_respondd.aggregator.logger.error") as mock_log_error:
            result = get_infos(cfg)

        assert [ap.name for ap in result] == ["ap2"]
        mock_log_error.assert_called_once()
        assert "does-not-exist" in mock_log_error.call_args[0][0]

    @patch("unifi_respondd.aggregator.net.scrape")
    def test_all_controllers_failing_returns_empty_list_not_none(self, mock_scrape):
        mock_scrape.return_value = {"nodes": []}
        cfg = make_config([make_controller_cfg("unifi", "broken")])

        def raise_error(*args, **kwargs):
            raise Exception("connection refused")

        with patch.dict(
            "unifi_respondd.aggregator.VENDOR_CLIENTS",
            {"unifi": Mock(side_effect=raise_error)},
        ):
            result = get_infos(cfg)

        assert result == []
        assert result is not None

    @patch("unifi_respondd.aggregator.net.scrape")
    def test_scrapes_nodelist_exactly_once(self, mock_scrape):
        mock_scrape.return_value = {"nodes": []}
        cfg = make_config(
            [
                make_controller_cfg("unifi", "a"),
                make_controller_cfg("omada", "b"),
            ]
        )

        with patch.dict(
            "unifi_respondd.aggregator.VENDOR_CLIENTS",
            {
                "unifi": Mock(return_value=[]),
                "omada": Mock(return_value=[]),
            },
        ):
            get_infos(cfg)

        mock_scrape.assert_called_once_with(cfg.nodelist)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
