#!/usr/bin/env python3

import dataclasses
from typing import List, Optional


@dataclasses.dataclass
class Radio:
    """This class contains the information of a radio serving the Freifunk SSID.
    Attributes:
        frequency: The frequency of the radio in MHz.
        rx_bytes: The received bytes on this radio.
        tx_bytes: The transmitted bytes on this radio."""

    frequency: Optional[int]
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None


@dataclasses.dataclass
class Accesspoint:
    """This class contains the controller independent information of an AP.
    Every backend maps its controller data to this model.
    Attributes:
        name: The name of the AP.
        mac: The MAC address of the AP.
        latitude: The latitude of the AP, 0 if unknown, None to omit it.
        longitude: The longitude of the AP, 0 if unknown, None to omit it.
        model: The hardware model of the AP.
        firmware: The firmware release of the AP.
        firmware_base: The firmware base shown on the map, e.g. "UniFi".
        domain_code: The Freifunk domain of the AP.
        contact: The contact of the AP for example an email address.
        uptime: The uptime of the AP in seconds.
        load_avg: The load average of the AP.
        mem_total: The total memory of the AP in bytes.
        mem_used: The used memory of the AP in bytes.
        mem_buffer: The buffer memory of the AP in bytes.
        tx_bytes: The transmitted bytes of the AP.
        rx_bytes: The received bytes of the AP.
        client_count: The number of clients connected to the AP.
        client_count24: The number of clients connected to the AP via 2,4 GHz.
        client_count5: The number of clients connected to the AP via 5 GHz.
        gateway: The MAC of the IPv4 Gateway.
        gateway6: The MAC of the IPv6 Gateway.
        gateway_nexthop: The MAC of the nexthop Gateway.
        neighbour_macs: The MACs of the mesh neighbours of the AP.
        radios: The radios serving the Freifunk SSID."""

    name: str
    mac: str
    latitude: Optional[float]
    longitude: Optional[float]
    model: str
    firmware: str
    firmware_base: str
    domain_code: str
    contact: Optional[str] = None
    uptime: Optional[int] = None
    load_avg: Optional[float] = None
    mem_total: Optional[int] = None
    mem_used: Optional[int] = None
    mem_buffer: Optional[int] = None
    tx_bytes: Optional[int] = None
    rx_bytes: Optional[int] = None
    client_count: Optional[int] = None
    client_count24: Optional[int] = None
    client_count5: Optional[int] = None
    gateway: Optional[str] = None
    gateway6: Optional[str] = None
    gateway_nexthop: Optional[str] = None
    neighbour_macs: List[str] = dataclasses.field(default_factory=list)
    radios: List[Radio] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Accesspoints:
    """This class contains the information of all APs.
    Attributes:
        accesspoints: A list of Accesspoint objects."""

    accesspoints: List[Accesspoint]
