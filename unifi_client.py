#!/usr/bin/env python3

from json import load
from geopy.point import Point
from unificontrol import UnifiClient
from typing import List
from geopy.geocoders import Nominatim
import time
import dataclasses
import config


@dataclasses.dataclass
class Accesspoint:
    """This class contains the information of an AP.
    Attributes:
        name: The name of the AP (alias in the unifi controller).
        mac: The MAC address of the AP.
        snmp_location: The location of the AP (SNMP location in the unifi controller).
        client_count: The number of clients connected to the AP.
        client_count24: The number of clients connected to the AP via 2,4 GHz.
        client_count5: The number of clients connected to the AP via 5 GHz.
        latitude: The latitude of the AP.
        longitude: The longitude of the AP.
        model: The hardware model of the AP.
        firmware: The firmware information of the AP.
        uptime: The uptime of the AP.
        contact: The contact of the AP for example an email address.
        load_avg: The load average of the AP.
        mem_used: The used memory of the AP.
        mem_total: The total memory of the AP.
        mem_buffer: The buffer memory of the AP.
        tx_bytes: The transmitted bytes of the AP.
        rx_bytes: The received bytes of the AP."""

    name: str
    mac: str
    snmp_location: str
    client_count: int
    client_count24: int
    client_count5: int
    latitude: float
    longitude: float
    model: str
    firmware: str
    uptime: int
    contact: str
    load_avg: float
    mem_used: int
    mem_total: int
    mem_buffer: int
    tx_bytes: int
    rx_bytes: int


@dataclasses.dataclass
class Accesspoints:
    """This class contains the information of all APs.
    Attributes:
        accesspoints: A list of Accesspoint objects."""

    accesspoints: List[Accesspoint]


def get_sites(cfg):
    """This function returns a list of sites."""
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
    )
    client.login()
    sites = client.list_sites()
    return sites


def get_aps(cfg, site):
    """This function returns a list of APs."""
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
        site=site,
    )
    client.login()
    aps = client.list_devices()
    return aps


def get_clients_for_site(cfg, site):
    client = UnifiClient(
        host=cfg.controller_url,
        port=cfg.controller_port,
        username=cfg.username,
        password=cfg.password,
        cert=None,
        site=site,
    )
    client.login()
    clients = client.list_clients()
    return clients


def get_client_count_for_ap(ap_mac, clients):
    client5_count = 0
    client24_count = 0
    for client in clients:
        if client.get("ap_mac", "No mac") == ap_mac:
            if client.get("channel", 0) > 14:
                client5_count += 1
            else:
                client24_count += 1
    return client24_count + client5_count, client24_count, client5_count


def get_location_by_address(address, app):
    """This function returns latitude and longitude of a given address."""
    time.sleep(1)
    try:
        point = Point().from_string(address)
        return point.latitude, point.longitude
    except:
        try:
            return app.geocode(address).raw["lat"], app.geocode(address).raw["lon"]
        except:
            return get_location_by_address(address)


def get_infos():
    cfg = config.Config.from_dict(config.load_config())
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    aps = Accesspoints(accesspoints=[])
    for site in get_sites(cfg):
        aps_for_site = get_aps(cfg, site["name"])
        clients = get_clients_for_site(cfg, site["name"])
        for ap in aps_for_site:
            if ap.get("name", None) is not None and ap.get("state", 0) != 0:
                client_count, client_count24, client_count5 = get_client_count_for_ap(
                    ap.get("mac", None), clients
                )
                lat, lon = 0, 0
                if ap.get("snmp_location", None) is not None:
                    try:
                        lat, lon = get_location_by_address(
                            ap["snmp_location"], geolookup
                        )
                    except:
                        pass
                aps.accesspoints.append(
                    Accesspoint(
                        name=ap.get("name", None),
                        mac=ap.get("mac", None),
                        snmp_location=ap.get("snmp_location", None),
                        client_count=client_count,
                        client_count24=client_count24,
                        client_count5=client_count5,
                        latitude=float(lat),
                        longitude=float(lon),
                        model=ap.get("model", None),
                        firmware=ap.get("version", None),
                        uptime=ap.get("uptime", None),
                        contact=ap.get("snmp_contact", None),
                        load_avg=float(ap.get("sys_stats", {}).get("loadavg_1", 0.0)),
                        mem_used=ap.get("sys_stats", {}).get("mem_used", 0),
                        mem_buffer=ap.get("sys_stats", {}).get("mem_buffer", 0),
                        mem_total=ap.get("sys_stats", {}).get("mem_total", 0),
                        tx_bytes=ap.get("tx_bytes", 0),
                        rx_bytes=ap.get("rx_bytes", 0),
                    )
                )
    return aps


def main():
    print(get_infos())


if __name__ == "__main__":
    main()
