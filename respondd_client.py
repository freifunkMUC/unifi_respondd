#!/usr/bin/env python3

import socket
import struct
import json
import zlib
import time

import dataclasses
from dataclasses_json import dataclass_json
import unifi_client


@dataclasses.dataclass
class FirmwareInfo:
    """This class contains the firmware information of an AP.
    Attributes:
        base: The base version of the firmware.
        release: The release version of the firmware."""

    base: str
    release: str


@dataclasses.dataclass
class LocationInfo:
    """This class contains the location information of an AP.
    Attributes:
        latitude: The latitude of the AP.
        longitude: The longitude of the AP."""

    latitude: float
    longitude: float


@dataclasses.dataclass
class HardwareInfo:
    """This class contains the hardware information of an AP.
    Attributes:
        model: The hardware model of the AP."""

    model: str


@dataclasses.dataclass
class OwnerInfo:
    """This class contains the owner information of an AP.
    Attributes:
        contact: The contact of the AP for example an email address."""

    contact: str


@dataclasses.dataclass
class SoftwareInfo:
    """This class contains the software information of an AP.
    Attributes:
        firmware: The firmware information of the AP."""

    firmware: FirmwareInfo


@dataclasses.dataclass
class NetworkInfo:
    """This class contains the network information of an AP.
    Attributes:
        mac: The MAC address of the AP."""

    mac: str


@dataclass_json
@dataclasses.dataclass
class NodeInfo:
    """This class contains the node information of an AP.
    Attributes:
        software: The software information of the AP.
        hostname: The hostname of the AP.
        node_id: The node id of the AP. This is the same as the MAC address (without :).
        location: The location information of the AP.
        hardware: The hardware information of the AP.
        owner: The owner information of the AP.
        network: The network information of the AP."""

    software: SoftwareInfo
    hostname: str
    node_id: str
    location: LocationInfo
    hardware: HardwareInfo
    owner: OwnerInfo
    network: NetworkInfo


@dataclasses.dataclass
class ClientInfo:
    """This class contains the client information of an AP.
    Attributes:
        total: The total number of clients.
        wifi: The number of clients connected via WiFi.
        wifi24: The number of clients connected via 2,4ghz WiFi.
        wifi5: The number of clients connected via 5ghz WiFi."""

    total: int
    wifi: int
    wifi24: int
    wifi5: int


@dataclasses.dataclass
class MemoryInfo:
    """This class contains the memory information of an AP.
    Attributes:
        total: The total memory of the AP.
        free: The free memory of the AP.
        buffers: The buffer memory of the AP."""

    total: int
    free: int
    buffers: int


@dataclasses.dataclass
class txInfo:
    """This class contains the tx information of an AP.
    Attributes:
        bytes: The number of bytes transmitted."""

    bytes: int


@dataclasses.dataclass
class rxInfo:
    """This class contains the rx information of an AP.
    Attributes:
        bytes: The number of bytes received."""

    bytes: int


@dataclasses.dataclass
class TrafficInfo:
    """This class contains the traffic information of an AP.
    Attributes:
        tx: The tx information of the AP.
        rx: The rx information of the AP."""

    tx: txInfo
    rx: rxInfo


@dataclass_json
@dataclasses.dataclass
class StatisticsInfo:
    """This class contains the statistics information of an AP.
    Attributes:
        clients: The client information of the AP.
        uptime: The uptime of the AP.
        node_id: The node id of the AP. This is the same as the MAC address (without :).
        loadavg: The load average of the AP.
        memory: The memory information of the AP.
        traffic: The traffic information of the AP."""

    clients: ClientInfo
    uptime: int
    node_id: str
    loadavg: float
    memory: MemoryInfo
    traffic: TrafficInfo


class ResponddClient:
    """This class receives a request from the respondd server and returns the response."""

    def __init__(self, config):
        self._config = config
        self._sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

    @property
    def _aps(self):
        return unifi_client.get_infos()

    @property
    def _nodeinfos(self):
        return self.getNodeInfos()

    @property
    def _statistics(self):
        return self.getStatistics()

    @staticmethod
    def joinMCAST(sock, addr, ifname):
        """Joins a multicast group on a socket."""
        group = socket.inet_pton(socket.AF_INET6, addr)
        if_idx = socket.if_nametoindex(ifname)
        sock.setsockopt(
            socket.IPPROTO_IPV6,
            socket.IPV6_JOIN_GROUP,
            group + struct.pack("I", if_idx),
        )

    def getNodeInfos(self):
        """This method returns the node information of all APs."""
        aps = self._aps
        nodes = []
        for ap in aps.accesspoints:
            nodes.append(
                NodeInfo(
                    software=SoftwareInfo(
                        firmware=FirmwareInfo(base=ap.firmware, release="")
                    ),
                    hostname=ap.name,
                    node_id=ap.mac.replace(":", ""),
                    location=LocationInfo(latitude=ap.latitude, longitude=ap.longitude),
                    hardware=HardwareInfo(model=ap.model),
                    owner=OwnerInfo(contact=ap.contact),
                    network=NetworkInfo(mac=ap.mac),
                )
            )
        return nodes

    def getStatistics(self):
        """This method returns the statistics information of all APs."""
        aps = self._aps
        statistics = []
        for ap in aps.accesspoints:
            statistics.append(
                StatisticsInfo(
                    clients=ClientInfo(
                        total=ap.client_count,
                        wifi=ap.client_count,
                        wifi24=ap.client_count24,
                        wifi5=ap.client_count5,
                    ),
                    uptime=ap.uptime,
                    node_id=ap.mac.replace(":", ""),
                    loadavg=ap.load_avg,
                    memory=MemoryInfo(
                        total=int(ap.mem_total / 1024),
                        free=int((ap.mem_total - ap.mem_used) / 1024),
                        buffers=int(ap.mem_buffer / 1024),
                    ),
                    traffic=TrafficInfo(
                        tx=txInfo(bytes=int(ap.tx_bytes)),
                        rx=rxInfo(bytes=int(ap.rx_bytes)),
                    ),
                )
            )
        return statistics

    def listenMulticast(self):
        msg, sourceAddress = self._sock.recvfrom(2048)
        if self._config.verbose:
            print("Using multicast method")
        msgSplit = str(msg, "UTF-8").split(" ")

        return msgSplit, sourceAddress

    def sendUnicast(self):
        timeStart = time.time()

        if self._config.verbose:
            print("Using unicast method")

        timeStop = time.time()
        timeSleep = int(60 - (timeStop - timeStart) % 60)
        if self._config.verbose:
            print("will now sleep " + str(timeSleep) + " seconds")
        time.sleep(timeSleep)

    def start(self):
        """This method starts the respondd client."""
        self._sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BINDTODEVICE,
            bytes(self._config.interface.encode()),
        )
        if self._config.multicast_enabled:
            self._sock.bind(("::", self._config.multicast_port))

            self.joinMCAST(
                self._sock, self._config.multicast_address, self._config.interface
            )

        while True:
            responseStruct = {}
            sourceAddress = (self._config.unicast_address, self._config.unicast_port)
            msgSplit = ["GET", "nodeinfo", "statistics"]

            if self._config.multicast_enabled:
                msgSplit, sourceAddress = self.listenMulticast()
            else:
                self.sendUnicast()
            if msgSplit[0] == "GET":  # multi_request
                for request in msgSplit[1:]:
                    responseStruct[request] = self.buildStruct(request)
                self.sendStruct(sourceAddress, responseStruct, True)
            else:  # single_request
                responseStruct = self.buildStruct(msgSplit[0])
                self.sendStruct(sourceAddress, responseStruct, False)

    def merge_node(self, responseStruct):
        """This method merges the node information of all APs to their corresponding node_id."""
        merged = {}
        for key in responseStruct.keys():
            print(key)
            if responseStruct[key]:
                for info in responseStruct[key]:
                    if info.node_id not in merged:
                        merged[info.node_id] = {key: info}
                    else:
                        merged[info.node_id].update({key: info})
        return merged

    def buildStruct(self, responseType):
        """This method builds the response structure."""

        responseClass = None
        if responseType == "statistics":
            responseClass = self._statistics
        elif responseType == "nodeinfo":
            responseClass = self._nodeinfos
        else:
            print("unknown command: " + responseType)
            return

        return responseClass

    def sendStruct(self, destAddress, responseStruct, withCompression):
        """This method sends the response structure to the respondd server."""
        if self._config.verbose:
            print(
                "%14.3f %35s %5d: " % (time.time(), destAddress[0], destAddress[1]),
                end="",
            )
            print(responseStruct)
        merged = self.merge_node(responseStruct)
        for infos in merged.values():
            node = {}
            for key, info in infos.items():
                node.update({key: info.to_dict()})
            responseData = bytes(json.dumps(node), "UTF-8")
            print(responseData)

            if withCompression:
                encoder = zlib.compressobj(
                    zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15
                )
                responseData = encoder.compress(responseData)
                responseData += encoder.flush()

            self._sock.sendto(responseData, destAddress)
