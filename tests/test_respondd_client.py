#!/usr/bin/env python3
"""Unit tests for unified_respondd/respondd_client.py module."""

import json
import zlib
from unittest.mock import Mock, patch

import pytest

from unified_respondd.config import Controller
from unified_respondd.model import Accesspoint, Accesspoints, Radio
from unified_respondd.respondd_client import ResponddClient, parse_request


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


def make_client(*names):
    """Returns a client with a mock backend per controller name."""
    controllers = [Controller(name, "unifi", Mock(), "report") for name in names]
    config = Mock(verbose=False, controllers=controllers)
    with (
        patch("unified_respondd.respondd_client.socket.socket"),
        patch(
            "unified_respondd.respondd_client.backends.load",
            side_effect=lambda name: Mock(),
        ),
    ):
        return ResponddClient(config)


@pytest.fixture
def client():
    client = make_client("unifi")
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

    def test_send_single_request(self, client):
        """A single request is answered with the bare, uncompressed object."""
        response = client.buildStruct("statistics")
        client.sendStruct(("fe80::1", 10001), {"statistics": response}, False)

        data, _ = client._sock.sendto.call_args.args
        assert json.loads(data)["node_id"] == "020000000010"
        assert "uptime" in json.loads(data)


class TestUnknownLocation:
    @pytest.fixture
    def aps(self, client):
        located = make_ap()
        unknown = make_ap(
            name="NoLocation", mac="02:00:00:00:00:11", latitude=0, longitude=0
        )
        controller, backend = client._backends[0]
        backend.get_infos.return_value = Accesspoints(accesspoints=[located, unknown])
        return client

    def mode(self, client, mode):
        client._backends[0][0].unknown_location = mode

    def test_report(self, aps):
        nodes = aps.collect()
        assert nodes["020000000011"]["nodeinfo"]["location"] == {
            "latitude": 0,
            "longitude": 0,
        }

    def test_omit(self, aps):
        self.mode(aps, "omit")
        nodes = aps.collect()
        assert "location" not in nodes["020000000011"]["nodeinfo"]
        assert "statistics" in nodes["020000000011"]
        assert nodes["020000000010"]["nodeinfo"]["location"]["latitude"] == 48.1351

    def test_skip(self, aps):
        self.mode(aps, "skip")
        assert list(aps.collect()) == ["020000000010"]

    def test_only_exactly_zero_is_unknown(self, aps):
        self.mode(aps, "skip")
        aps._backends[0][1].get_infos.return_value.accesspoints[1].longitude = 11.5
        assert len(aps.collect()) == 2

    def test_backend_error(self, aps):
        self.mode(aps, "skip")
        aps._backends[0][1].get_infos.return_value = None
        assert aps.collect() is None


class TestMultipleControllers:
    @pytest.fixture
    def client(self):
        client = make_client("omada", "unifi")
        (_, omada), (_, unifi) = client._backends
        omada.get_infos.return_value = Accesspoints(
            accesspoints=[make_ap(name="OmadaAP", mac="02:00:00:00:00:20")]
        )
        unifi.get_infos.return_value = Accesspoints(
            accesspoints=[make_ap(name="UnifiAP", mac="02:00:00:00:00:30")]
        )
        return client

    def test_all_controllers(self, client):
        nodes = client.collect()
        assert sorted(node["nodeinfo"]["hostname"] for node in nodes.values()) == [
            "OmadaAP",
            "UnifiAP",
        ]
        assert client.failed_controllers == []

    def test_each_controller_gets_its_config(self, client):
        client.collect()
        for controller, backend in client._backends:
            backend.get_infos.assert_called_once_with(controller.config)

    def test_failing_controller_is_skipped(self, client):
        client._backends[0][1].get_infos.return_value = None
        with patch("unified_respondd.respondd_client.logger.error") as error:
            nodes = client.collect()
        assert [node["nodeinfo"]["hostname"] for node in nodes.values()] == ["UnifiAP"]
        assert client.failed_controllers == ["omada"]
        error.assert_called_once()

    def test_all_controllers_failing(self, client):
        for _, backend in client._backends:
            backend.get_infos.return_value = None
        assert client.collect() is None
        assert client.failed_controllers == ["omada", "unifi"]

    def test_failed_controllers_reset(self, client):
        client._backends[0][1].get_infos.return_value = None
        client.collect()
        client._backends[0][1].get_infos.return_value = Accesspoints(accesspoints=[])
        client.collect()
        assert client.failed_controllers == []

    def test_unknown_location_per_controller(self, client):
        (omada_controller, omada), (_, unifi) = client._backends
        omada_controller.unknown_location = "skip"
        for backend in (omada, unifi):
            backend.get_infos.return_value.accesspoints[0].latitude = 0
            backend.get_infos.return_value.accesspoints[0].longitude = 0
        nodes = client.collect()
        assert [node["nodeinfo"]["hostname"] for node in nodes.values()] == ["UnifiAP"]


class TestParseRequest:
    @pytest.mark.parametrize(
        "msg,expected",
        [
            (
                b"GET nodeinfo statistics neighbours",
                (["nodeinfo", "statistics", "neighbours"], True),
            ),
            (b"GET statistics\n", (["statistics"], True)),
            (b"nodeinfo", (["nodeinfo"], False)),
            (b"GET nodeinfo foo", (["nodeinfo"], True)),
        ],
    )
    def test_valid(self, msg, expected):
        assert parse_request(msg) == expected

    @pytest.mark.parametrize(
        "msg", [b"", b"   ", b"GET", b"GET foo", b"foo", b"\xff\xfe GET nodeinfo"]
    )
    def test_invalid(self, msg):
        assert parse_request(msg) is None


class TestMulticastLoop:
    """Requests come from the network, no request may stop the service."""

    @pytest.fixture
    def multicast(self, client):
        client._config.multicast_enabled = True
        client._config.interface = "eth0"
        client._backends[0][1].get_infos.return_value = Accesspoints(
            accesspoints=[make_ap()]
        )
        client._sock = Mock()
        client.joinMCAST = Mock()
        return client

    def run(self, client, *packets):
        client._sock.recvfrom.side_effect = [
            *((packet, ("fe80::1", 1001)) for packet in packets),
            KeyboardInterrupt,
        ]
        with pytest.raises(KeyboardInterrupt):
            client.start()
        return [call.args for call in client._sock.sendto.call_args_list]

    def test_invalid_requests_are_ignored(self, multicast):
        sent = self.run(multicast, b"\xff\xfe", b"foo", b"GET", b"GET nodeinfo")
        assert len(sent) == 1
        data, address = sent[0]
        assert address == ("fe80::1", 1001)
        assert (
            json.loads(zlib.decompress(data, -15))["nodeinfo"]["hostname"] == "TestAP"
        )

    def test_single_request(self, multicast):
        [(data, _)] = self.run(multicast, b"nodeinfo")
        assert json.loads(data)["hostname"] == "TestAP"

    def test_requests_are_answered_from_cache(self, multicast):
        sent = self.run(multicast, b"GET nodeinfo", b"GET statistics", b"nodeinfo")
        assert len(sent) == 3
        multicast._backends[0][1].get_infos.assert_called_once()

    def test_cache_expires(self, multicast):
        with patch("unified_respondd.respondd_client.time.monotonic") as monotonic:
            monotonic.side_effect = [0, 10, 31]
            self.run(multicast, b"nodeinfo", b"nodeinfo", b"nodeinfo")
        assert multicast._backends[0][1].get_infos.call_count == 2

    def test_failed_fetch_is_cached_too(self, multicast):
        multicast._backends[0][1].get_infos.return_value = None
        assert self.run(multicast, b"nodeinfo", b"nodeinfo") == []
        multicast._backends[0][1].get_infos.assert_called_once()
