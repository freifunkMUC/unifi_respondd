#!/usr/bin/env python3

import dataclasses
from typing import List, Optional


@dataclasses.dataclass
class WirelessBandInfo:
    """One radio band's frequency plus optional per-band traffic counters.
    Attributes:
        frequency: The frequency of the band in MHz.
        rx_bytes: The received bytes on this band, if the vendor reports per-band traffic.
        tx_bytes: The transmitted bytes on this band, if the vendor reports per-band traffic.
    """

    frequency: int
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None


@dataclasses.dataclass
class Accesspoint:
    """Vendor-agnostic representation of one Access Point, produced by a
    vendor client module (unifi_respondd/vendors/*.py) and consumed by
    respondd_client.py.
    Attributes:
        name: The name of the AP (alias in the controller).
        mac: The MAC address of the AP.
        controller_type: The registry key of the vendor client that produced this AP (e.g. "unifi", "omada").
        controller_name: The name of the controller instance that produced this AP.
        firmware_base: The wire-protocol firmware base label (e.g. "UniFi", "Omada").
        snmp_location: The location of the AP (SNMP location in the controller).
        latitude: The latitude of the AP.
        longitude: The longitude of the AP.
        contact: The contact of the AP for example an email address.
        model: The hardware model of the AP.
        firmware: The firmware information of the AP.
        uptime: The uptime of the AP.
        client_count: The number of clients connected to the AP.
        client_count24: The number of clients connected to the AP via 2,4 GHz.
        client_count5: The number of clients connected to the AP via 5 GHz.
        wireless_bands: The wireless band information of the AP.
        tx_bytes: The transmitted bytes of the AP.
        rx_bytes: The received bytes of the AP.
        load_avg: The load average of the AP.
        mem_used: The used memory of the AP.
        mem_total: The total memory of the AP.
        mem_buffer: The buffer memory of the AP.
        gateway: The MAC of the IPv4 Gateway.
        gateway6: The MAC of the IPv6 Gateway.
        gateway_nexthop: The MAC of the nexthop Gateway.
        neighbour_macs: The MAC addresses of the AP's neighbours.
        domain_code: The domain code of the AP."""

    name: str
    mac: str
    controller_type: str
    controller_name: str
    firmware_base: str

    snmp_location: Optional[str]
    latitude: float
    longitude: float
    contact: Optional[str]

    model: str
    firmware: str
    uptime: int

    client_count: int
    client_count24: int
    client_count5: int

    wireless_bands: List[WirelessBandInfo]
    tx_bytes: int
    rx_bytes: int

    load_avg: float
    mem_used: int
    mem_total: int
    mem_buffer: int

    gateway: Optional[str]
    gateway6: Optional[str]
    gateway_nexthop: Optional[str]
    neighbour_macs: List[str]
    domain_code: str
