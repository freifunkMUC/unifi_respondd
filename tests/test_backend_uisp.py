#!/usr/bin/env python3
"""Unit tests for unified_respondd/backends/uisp.py module."""

import copy
from unittest.mock import patch

import pytest

from unified_respondd.backends import uisp
from unified_respondd.backends.uisp import (
    ControllerConfig,
    get_client_total,
    get_infos,
    get_link_count,
    get_loadavg,
    get_model,
    get_traffic_bytes,
    get_uptime,
    get_uptime_from_interfaces,
)

BASE = "https://uisp.example.org/nms/api/v2.1"
UISP_CONFIG = {"controller_url": BASE, "token": "synthetic-token"}


def series(*values):
    return [{"x": i, "y": y} for i, y in enumerate(values)]


def device(i, name, overview=None, **identification):
    return {
        "identification": {
            "id": f"d{i}",
            "hostname": name,
            "name": name,
            "mac": f"fc:ec:da:00:00:0{i}",
            "firmwareVersion": "2.6.0",
            "model": "AF60-LR",
            "type": "airFiber",
            **identification,
        },
        "location": {"latitude": 48.1, "longitude": 11.5},
        "overview": {"status": "active", **(overview or {})},
    }


def link(a, b):
    return {
        "from": {"device": {"identification": {"name": a}}},
        "to": {"device": {"identification": {"name": b}}},
    }


DEVICES = [
    device(1, "AF-A", {"uptime": 1000, "cpu": 20, "ram": 50, "stationsCount": 1}),
    device(2, "AF-B"),
    device(3, "BB", type="blackBox", model="UNKNOWN", firmwareVersion=None),
    device(4, "Router-1"),
    device(5, "OFF", {"status": "disconnected"}),
]
LINKS = [link("AF-A", "AF-B"), link("AF-B", "AF-A")]
STATS = {
    "d1": {
        "interfaces": [
            {"txBytes": {"avg": series(1, 100)}, "rxBytes": {"avg": series(2, 200)}}
        ]
    },
    "d2": {"utilization": {"avg": series(0.2, 0.456)}},
}
STATIONS = {"d2": [{"uptime": 4000, "txBytes": 300, "rxBytes": 400}]}


@pytest.fixture
def cfg():
    return ControllerConfig.from_dict(UISP_CONFIG)


@pytest.fixture
def api():
    """Serves synthetic UISP API responses and records the requested paths."""
    data = {
        "devices": copy.deepcopy(DEVICES),
        "links": copy.deepcopy(LINKS),
        "requests": [],
    }

    def fake_scrape(url, token):
        assert token == "synthetic-token"
        path = url[len(BASE) :]
        data["requests"].append(path)
        parts = path.split("/")
        if path == "/devices":
            return data["devices"]
        if path == "/data-links":
            return data["links"]
        if path.endswith("/statistics?interval=hour"):
            return STATS.get(parts[2], "")
        if path.endswith("/interfaces"):
            return ""
        if path.endswith("/stations"):
            return STATIONS.get(parts[3], "")
        raise AssertionError(url)

    with patch.object(uisp, "scrape", fake_scrape):
        yield data


class TestControllerConfig:
    def test_from_dict(self):
        cfg = ControllerConfig.from_dict({**UISP_CONFIG, "controller_port": 443})
        assert cfg.controller_url == BASE
        assert cfg.token == "synthetic-token"
        assert cfg.fallback_domain == "uisp_respondd_fallback"

    def test_fallback_domain(self):
        cfg = ControllerConfig.from_dict({**UISP_CONFIG, "fallback_domain": "ffmuc"})
        assert cfg.fallback_domain == "ffmuc"


class TestScrape:
    @patch("unified_respondd.backends.uisp.rget")
    def test_token_and_timeout(self, rget):
        rget.return_value.json.return_value = [{"id": 1}]
        assert uisp.scrape(BASE + "/devices", "t") == [{"id": 1}]
        rget.assert_called_once_with(
            BASE + "/devices", headers={"X-Auth-Token": "t"}, timeout=30
        )

    @patch("unified_respondd.backends.uisp.rget", side_effect=Exception("timeout"))
    def test_error_is_logged(self, rget):
        with patch.object(uisp.logger, "error") as error:
            assert uisp.scrape(BASE + "/devices", "t") == ""
        error.assert_called_once()


class TestHelpers:
    @pytest.mark.parametrize(
        "identification,model",
        [
            ({"model": "AF60-LR"}, "AF60-LR"),
            ({"model": "UNKNOWN", "modelName": "airFiber 60"}, "airFiber 60"),
            ({"model": "UNKNOWN", "type": "blackBox"}, "blackBox"),
            ({}, "UNKNOWN"),
        ],
    )
    def test_get_model(self, identification, model):
        assert get_model({"identification": identification}) == model

    @pytest.mark.parametrize(
        "overview,uptime",
        [
            ({"uptime": 1000}, 1000),
            ({"serviceUptime": 2000}, 2000),
            ({"uptime": 2_000_000_000}, 2_000_000),  # milliseconds
            ({"uptime": 200_000_000}, None),  # implausible
            ({"uptime": 0}, None),
            ({}, None),
        ],
    )
    def test_get_uptime(self, overview, uptime):
        assert get_uptime({"overview": overview}) == uptime

    def test_uptime_from_preferred_interface(self):
        interfaces = [
            {"identification": {"name": "eth1"}, "wireless": {"serviceUptime": 1}},
            {"identification": {"name": "main"}, "wireless": {"serviceUptime": 5000}},
        ]
        assert get_uptime_from_interfaces(interfaces) == 5000
        assert get_uptime({"overview": {}}, interfaces=interfaces) == 5000

    def test_traffic_bytes_sums_latest_values(self):
        stats = {
            "interfaces": [
                {"txBytes": {"avg": series(1, 100)}, "rxBytes": {"sum": series(7)}},
                {"txBytes": {"max": series(5)}, "rxBytes": {}},
            ]
        }
        assert get_traffic_bytes(stats) == (105, 7)

    def test_traffic_bytes_without_stats(self):
        assert get_traffic_bytes(None) == (None, None)

    def test_loadavg_from_cpu(self):
        assert get_loadavg({"overview": {"cpu": 150}}) == 1.0

    def test_loadavg_from_utilization(self):
        stats = {"utilization": {"avg": series(0.2, 0.4567)}}
        assert get_loadavg({"overview": {}}, stats) == 0.457

    def test_loadavg_without_telemetry(self):
        assert get_loadavg({"overview": {}}, None) is None

    def test_client_total(self):
        assert get_client_total({"overview": {"linkStationsCount": 3}}) == 3
        assert get_client_total({"overview": {}}) is None

    def test_link_count(self):
        assert get_link_count([{}, {}]) == 2
        assert get_link_count([]) is None


class TestGetInfos:
    def test_devices(self, cfg, api):
        aps = get_infos(cfg).accesspoints
        assert [ap.name for ap in aps] == ["AF-A", "AF-B", "BB"]

    def test_device_with_overview_telemetry(self, cfg, api):
        ap = get_infos(cfg).accesspoints[0]
        assert ap.mac == "fc:ec:da:00:00:01"
        assert ap.model == "AF60-LR"
        assert ap.firmware == "2.6.0"
        assert ap.firmware_base == "UISP"
        assert (ap.latitude, ap.longitude) == (48.1, 11.5)
        assert ap.uptime == 1000
        assert ap.load_avg == 0.2
        assert (ap.mem_total, ap.mem_used, ap.mem_buffer) == (102400, 51200, 0)
        assert (ap.tx_bytes, ap.rx_bytes) == (100, 200)
        assert (ap.client_count, ap.client_count24, ap.client_count5) == (1, 0, 0)
        assert ap.domain_code == "uisp_respondd_fallback"

    def test_device_with_station_telemetry(self, cfg, api):
        ap = get_infos(cfg).accesspoints[1]
        assert ap.load_avg == 0.46
        assert (ap.tx_bytes, ap.rx_bytes) == (300, 400)
        assert ap.client_count == 1  # one link station

    def test_blackbox_without_telemetry(self, cfg, api):
        ap = get_infos(cfg).accesspoints[2]
        assert ap.model == "blackBox"
        assert ap.firmware == "unknown"
        assert ap.uptime == 0
        assert ap.load_avg == 0.0
        assert (ap.mem_total, ap.mem_used) == (102400, 0)
        assert (ap.tx_bytes, ap.rx_bytes) == (None, None)
        assert ap.client_count is None

    def test_neighbours_by_link(self, cfg, api):
        aps = get_infos(cfg).accesspoints
        assert aps[0].neighbour_macs == ["fc:ec:da:00:00:02"]
        assert aps[1].neighbour_macs == ["fc:ec:da:00:00:01"]
        assert aps[2].neighbour_macs == []

    def test_links_fetched_once(self, cfg, api):
        get_infos(cfg)
        assert api["requests"].count("/data-links") == 1

    def test_link_to_unknown_device(self, cfg, api):
        api["links"] = [link("AF-A", "GONE")]
        assert get_infos(cfg).accesspoints[0].neighbour_macs == []

    def test_no_devices(self, cfg, api):
        api["devices"] = ""
        assert get_infos(cfg).accesspoints == []
