#!/usr/bin/env python3

import dataclasses
import json
import socket
import struct
import time
import zlib
from typing import Dict, List, Optional

from dataclasses_json import config, dataclass_json

from unified_respondd import backends, logger
from unified_respondd.model import Accesspoints

OMIT_IF_NONE = config(exclude=lambda value: value is None)


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
    nproc: int = 1


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
class InterfacesInfo:
    other: List[str]


@dataclasses.dataclass
class IntInfo:
    interfaces: InterfacesInfo


@dataclasses.dataclass
class NetworkInfo:
    """This class contains the network information of an AP.
    Attributes:
        mac: The MAC address of the AP."""

    mac: str
    mesh: Dict[str, IntInfo]


@dataclasses.dataclass
class SystemInfo:
    domain_code: str


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
    # Omitted for APs without a location if unknown_location is "omit"
    location: Optional[LocationInfo] = dataclasses.field(metadata=OMIT_IF_NONE)
    hardware: HardwareInfo
    owner: OwnerInfo
    network: NetworkInfo
    system: SystemInfo


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
class WirelessInfo:
    """This class contains the Wireless information of an AP.
    Attributes:
        frequency:
        noise:
        active:
        busy:
        rx:
        tx:"""

    frequency: int
    # noise: int
    # active: int
    # busy: int
    # Not every controller reports traffic per radio (omada), omit it then
    rx: Optional[int] = dataclasses.field(default=None, metadata=OMIT_IF_NONE)
    tx: Optional[int] = dataclasses.field(default=None, metadata=OMIT_IF_NONE)


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
        traffic: The traffic information of the AP.
        gateway: The MAC of the IPv4 Gateway
        gateway6: The MAC of the IPv6 Gateway
        gateway_nexthop: The MAC of the nexthop Gateway
        wireless: The WirelessInfos of the AP"""

    clients: Optional[ClientInfo]
    uptime: int
    node_id: str
    loadavg: float
    memory: Optional[MemoryInfo]
    traffic: Optional[TrafficInfo]
    gateway: str
    gateway6: str
    gateway_nexthop: str
    wireless: List[WirelessInfo]


@dataclasses.dataclass
class NeighbourDetails:
    tq: int
    lastseen: float


@dataclasses.dataclass
class Neighbours:
    neighbours: Dict[str, NeighbourDetails]


@dataclass_json
@dataclasses.dataclass
class NeighboursInfo:
    node_id: str
    batadv: Dict[str, Neighbours]


REQUEST_TYPES = ("nodeinfo", "statistics", "neighbours")

# Seconds to answer multicast requests from the last query of the controllers
CACHE_SECONDS = 30


def parse_request(msg):
    """This function parses a respondd request received via multicast.
    "GET nodeinfo statistics" asks for several types (compressed response),
    "nodeinfo" for one (uncompressed response with the bare object).
    Returns the requested types and whether it is a multi request, or None if
    the request is invalid. Requests come from the network, so nothing here may raise.
    """
    try:
        words = msg.decode("utf-8").split()
    except UnicodeDecodeError:
        logger.debug("Ignoring request that isn't UTF-8")
        return None
    multi = bool(words) and words[0] == "GET"
    requested = words[1:] if multi else words[:1]
    types = [request for request in requested if request in REQUEST_TYPES]
    if len(types) < len(requested):
        logger.debug("Ignoring unknown request types in %r", requested)
    if not types:
        return None
    return types, multi


def has_unknown_location(ap):
    """Backends report 0/0 if the location of an AP isn't set."""
    return ap.latitude == 0 and ap.longitude == 0


def apply_unknown_location(controller, accesspoints):
    """This function applies the unknown_location mode of the controller:
    "report" keeps 0/0, "omit" removes the location and "skip" the AP."""
    if controller.unknown_location == "report":
        return accesspoints
    unknown = [ap for ap in accesspoints if has_unknown_location(ap)]
    if controller.unknown_location == "skip":
        if unknown:
            logger.debug(
                "Skipping %d APs without a location of controller %s",
                len(unknown),
                controller.name,
            )
        return [ap for ap in accesspoints if not has_unknown_location(ap)]
    for ap in unknown:
        ap.latitude = ap.longitude = None
    return accesspoints


class ResponddClient:
    """This class receives a request from the respondd server and returns the response."""

    def __init__(self, config):
        self._config = config
        self._backends = [
            (controller, backends.load(controller.backend))
            for controller in config.controllers
        ]
        self.failed_controllers = []
        self._aps = None
        self._cached_aps = None
        self._fetched_at = None
        self._timeStart = time.time()
        self._timeStop = time.time()
        self._sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

    @property
    def _nodeinfos(self):
        return self.getNodeInfos()

    @property
    def _statistics(self):
        return self.getStatistics()

    @property
    def _neighbours(self):
        return self.getNeighbours()

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
                        firmware=FirmwareInfo(
                            base=ap.firmware_base, release=ap.firmware
                        )
                    ),
                    hostname=ap.name,
                    node_id=ap.mac.replace(":", ""),
                    location=(
                        None
                        if ap.latitude is None or ap.longitude is None
                        else LocationInfo(latitude=ap.latitude, longitude=ap.longitude)
                    ),
                    hardware=HardwareInfo(model=ap.model),
                    owner=OwnerInfo(contact=ap.contact),
                    network=NetworkInfo(
                        mac=ap.mac,
                        mesh={
                            "bat0": IntInfo(interfaces=InterfacesInfo(other=[ap.mac]))
                        },
                    ),
                    system=SystemInfo(domain_code=ap.domain_code),
                )
            )
        return nodes

    def getStatistics(self):
        """This method returns the statistics information of all APs."""
        aps = self._aps
        statistics = []
        for ap in aps.accesspoints:
            wirelessinfos = [
                WirelessInfo(
                    frequency=radio.frequency, rx=radio.rx_bytes, tx=radio.tx_bytes
                )
                for radio in ap.radios
            ]

            # Not every device reports all telemetry (e.g. UISP blackBox devices)
            clients = None
            if ap.client_count is not None:
                clients = ClientInfo(
                    total=ap.client_count,
                    wifi=ap.client_count,
                    wifi24=ap.client_count24,
                    wifi5=ap.client_count5,
                )
            memory = None
            if ap.mem_total is not None:
                memory = MemoryInfo(
                    total=int(ap.mem_total / 1024),
                    free=int((ap.mem_total - (ap.mem_used or 0)) / 1024),
                    buffers=int((ap.mem_buffer or 0) / 1024),
                )
            traffic = None
            if ap.tx_bytes is not None or ap.rx_bytes is not None:
                traffic = TrafficInfo(
                    tx=txInfo(bytes=int(ap.tx_bytes or 0)),
                    rx=rxInfo(bytes=int(ap.rx_bytes or 0)),
                )

            statistics.append(
                StatisticsInfo(
                    clients=clients,
                    uptime=ap.uptime,
                    node_id=ap.mac.replace(":", ""),
                    loadavg=ap.load_avg,
                    memory=memory,
                    traffic=traffic,
                    gateway=ap.gateway,
                    gateway6=ap.gateway6,
                    gateway_nexthop=ap.gateway_nexthop,
                    wireless=wirelessinfos,
                )
            )
        return statistics

    def getNeighbours(self):
        """This method returns the neighbour information of all APs."""
        aps = self._aps
        neighbours = []
        for ap in aps.accesspoints:
            nbs = {}
            for neighbour_mac in ap.neighbour_macs:
                if neighbour_mac is not None:
                    nbs[neighbour_mac] = NeighbourDetails(tq=255, lastseen=0.45)
            neighbours.append(
                NeighboursInfo(
                    node_id=ap.mac.replace(":", ""),
                    batadv={ap.mac: Neighbours(neighbours=nbs)},
                )
            )
        return neighbours

    def listenMulticast(self):
        """This method waits for a valid request and returns it with its sender."""
        while True:
            msg, sourceAddress = self._sock.recvfrom(2048)
            request = parse_request(msg)
            if request is not None:
                logger.debug("Using multicast method")
                return request, sourceAddress

    def sendUnicast(self):
        logger.info("Using unicast method")

        timeSleep = int(60 - (self._timeStop - self._timeStart) % 60)
        if self._config.verbose:
            logger.debug("will now sleep " + str(timeSleep) + " seconds")
        time.sleep(timeSleep)

    def start(self):
        """This method starts the respondd client."""
        # Only packets of the configured interface (e.g. bat0) reach the socket, so
        # binding to "::" below doesn't expose it on other interfaces. The wildcard
        # is needed to answer yanic's unicast requests to nodes that didn't answer
        # the multicast request, binding to the group would drop those.
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
            sourceAddress = (self._config.unicast_address, self._config.unicast_port)
            request = (list(REQUEST_TYPES), True)

            if self._config.multicast_enabled:
                request, sourceAddress = self.listenMulticast()
            else:
                self.sendUnicast()
            self._timeStart = time.time()
            self._aps = self.fetch_cached()
            if self._aps is None:
                continue
            types, multi = request
            responseStruct = {type: self.buildStruct(type) for type in types}
            self.sendStruct(sourceAddress, responseStruct, multi)
            self._timeStop = time.time()

    def fetch_cached(self):
        """This method returns the APs, in multicast mode fetched at most every
        CACHE_SECONDS. A flood of requests must not flood the controllers."""
        if not self._config.multicast_enabled:
            return self.fetch()
        now = time.monotonic()
        if self._fetched_at is None or now - self._fetched_at >= CACHE_SECONDS:
            self._cached_aps = self.fetch()
            self._fetched_at = now
        return self._cached_aps

    def fetch(self):
        """This method returns the APs of all controllers.
        A failing controller is logged, skipped and listed in failed_controllers.
        Returns None if all controllers failed."""
        self.failed_controllers = []
        accesspoints = []
        for controller, backend in self._backends:
            aps = backend.get_infos(controller.config)
            if aps is None:
                logger.error(
                    "Could not fetch the APs of controller %s", controller.name
                )
                self.failed_controllers.append(controller.name)
                continue
            accesspoints.extend(apply_unknown_location(controller, aps.accesspoints))
        if len(self.failed_controllers) == len(self._backends):
            return None
        return Accesspoints(accesspoints=accesspoints)

    def collect(self):
        """This method fetches the APs once and returns all responses per node_id.
        Returns None if the APs could not be fetched."""
        self._aps = self.fetch()
        if self._aps is None:
            return None
        responseStruct = {
            request: self.buildStruct(request)
            for request in ("nodeinfo", "statistics", "neighbours")
        }
        return {
            node_id: {key: info.to_dict() for key, info in infos.items()}
            for node_id, infos in self.merge_node(responseStruct).items()
        }

    def merge_node(self, responseStruct):
        """This method merges the node information of all APs to their corresponding node_id."""
        merged = {}
        for key in responseStruct.keys():
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
        elif responseType == "neighbours":
            responseClass = self._neighbours
        else:
            logger.warning("unknown command: %r", responseType)
            return

        return responseClass

    def sendStruct(self, destAddress, responseStruct, withCompression):
        """This method sends the response structure to the respondd server.
        A multi request (withCompression) gets all types per node, compressed,
        a single request the bare object of its type."""
        logger.debug("Sending %s to %s", list(responseStruct), destAddress)

        merged = self.merge_node(responseStruct)
        for infos in merged.values():
            if withCompression:
                node = {key: info.to_dict() for key, info in infos.items()}
            else:
                [info] = infos.values()
                node = info.to_dict()
            responseData = bytes(json.dumps(node), "UTF-8")
            logger.debug(str(responseData))

            if withCompression:
                encoder = zlib.compressobj(
                    zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15
                )
                responseData = encoder.compress(responseData)
                responseData += encoder.flush()

            self._sock.sendto(responseData, destAddress)
