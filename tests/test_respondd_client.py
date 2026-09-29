#!/usr/bin/env python3
"""Unit tests for unified_respondd/respondd_client.py module."""

import json
import zlib
from unittest.mock import Mock, patch

import pytest

from unified_respondd.model import Accesspoint, Accesspoints, Radio
from unified_respondd.respondd_client import ResponddClient


def make_ap(**kwargs):
    ap = dict(
        name="TestAP",
        mac="02:00:00:00:00:10",
        latitude=48.1351,
        longitude=11.5820,
        model="U6-LR",
        firmware="6.6.1",
        firmware_base="UniFi",
        domain_code="ffmuc_test",
        contact="noc@example.org",
        uptime=86400,
        load_avg=0.25,
        mem_total=512 * 1024,
        mem_used=256 * 1024,
        mem_buffer=16 * 1024,
        tx_bytes=2000,
        rx_bytes=1000,
        client_count=3,
        client_count24=1,
        client_count5=2,
        gateway="02:00:00:00:00:aa",
        gateway6="02:00:00:00:00:bb",
        gateway_nexthop="020000000001",
        neighbour_macs=["02:00:00:00:00:01", None],
        radios=[
            Radio(frequency=5180, rx_bytes=10, tx_bytes=20),
            Radio(frequency=2437, rx_bytes=30, tx_bytes=40),
        ],
    )
    ap.update(kwargs)
    return Accesspoint(**ap)


@pytest.fixture
def client():
    config = Mock(backend="unifi", verbose=False)
    with patch("unified_respondd.respondd_client.socket.socket"):
        client = ResponddClient(config)
    client._aps = Accesspoints(accesspoints=[make_ap()])
    return client


class TestNodeInfos:
    def test_nodeinfo(self, client):
        assert client.getNodeInfos()[0].to_dict() == {
            "software": {"firmware": {"base": "UniFi", "release": "6.6.1"}},
            "hostname": "TestAP",
            "node_id": "020000000010",
            "location": {"latitude": 48.1351, "longitude": 11.5820},
            "hardware": {"model": "U6-LR", "nproc": 1},
            "owner": {"contact": "noc@example.org"},
            "network": {
                "mac": "02:00:00:00:00:10",
                "mesh": {"bat0": {"interfaces": {"other": ["02:00:00:00:00:10"]}}},
            },
            "system": {"domain_code": "ffmuc_test"},
        }

    def test_firmware_base_from_backend(self, client):
        client._aps = Accesspoints(accesspoints=[make_ap(firmware_base="Omada")])
        assert client.getNodeInfos()[0].software.firmware.base == "Omada"


class TestStatistics:
    def test_statistics(self, client):
        assert client.getStatistics()[0].to_dict() == {
            "clients": {"total": 3, "wifi": 3, "wifi24": 1, "wifi5": 2},
            "uptime": 86400,
            "node_id": "020000000010",
            "loadavg": 0.25,
            "memory": {"total": 512, "free": 256, "buffers": 16},
            "traffic": {"tx": {"bytes": 2000}, "rx": {"bytes": 1000}},
            "gateway": "02:00:00:00:00:aa",
            "gateway6": "02:00:00:00:00:bb",
            "gateway_nexthop": "020000000001",
            "wireless": [
                {"frequency": 5180, "rx": 10, "tx": 20},
                {"frequency": 2437, "rx": 30, "tx": 40},
            ],
        }

    def test_missing_telemetry(self, client):
        ap = make_ap(
            client_count=None,
            client_count24=None,
            client_count5=None,
            mem_total=None,
            tx_bytes=None,
            rx_bytes=None,
        )
        client._aps = Accesspoints(accesspoints=[ap])
        statistics = client.getStatistics()[0].to_dict()
        assert statistics["clients"] is None
        assert statistics["memory"] is None
        assert statistics["traffic"] is None

    def test_partial_traffic(self, client):
        client._aps = Accesspoints(accesspoints=[make_ap(tx_bytes=None)])
        assert client.getStatistics()[0].to_dict()["traffic"] == {
            "tx": {"bytes": 0},
            "rx": {"bytes": 1000},
        }

    def test_no_radios(self, client):
        client._aps = Accesspoints(accesspoints=[make_ap(radios=[])])
        assert client.getStatistics()[0].wireless == []


class TestNeighbours:
    def test_neighbours_skip_none(self, client):
        assert client.getNeighbours()[0].to_dict() == {
            "node_id": "020000000010",
            "batadv": {
                "02:00:00:00:00:10": {
                    "neighbours": {"02:00:00:00:00:01": {"tq": 255, "lastseen": 0.45}}
                }
            },
        }


class TestBuildAndSend:
    def test_unknown_command(self, client):
        assert client.buildStruct("unknown") is None

    def test_merge_node(self, client):
        response = {
            "nodeinfo": client.buildStruct("nodeinfo"),
            "statistics": client.buildStruct("statistics"),
            "neighbours": None,
        }
        merged = client.merge_node(response)
        assert list(merged) == ["020000000010"]
        assert set(merged["020000000010"]) == {"nodeinfo", "statistics"}

    def test_send_compressed(self, client):
        response = {"nodeinfo": client.buildStruct("nodeinfo")}
        client.sendStruct(("fe80::1", 10001), response, True)

        data, address = client._sock.sendto.call_args.args
        assert address == ("fe80::1", 10001)
        payload = json.loads(zlib.decompress(data, -15))
        assert payload["nodeinfo"]["hostname"] == "TestAP"

    def test_send_uncompressed(self, client):
        response = client.buildStruct("statistics")
        client.sendStruct(("fe80::1", 10001), {"statistics": response}, False)

        data, _ = client._sock.sendto.call_args.args
        assert json.loads(data)["statistics"]["node_id"] == "020000000010"
