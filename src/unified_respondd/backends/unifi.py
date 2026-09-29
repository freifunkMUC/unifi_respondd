#!/usr/bin/env python3

import dataclasses
import re
from typing import Dict

from geopy.geocoders import Nominatim
from pyunifi.controller import Controller

from unified_respondd import logger
from unified_respondd.backends.common import (
    get_location_by_address,
    get_offloader,
    scrape,
)
from unified_respondd.model import Accesspoint, Accesspoints, Radio

ffnodes = None


@dataclasses.dataclass
class ControllerConfig:
    """The unifi specific part of the configuration file.
    Attributes:
        controller_url: The unifi controller URL.
        controller_port: The unifi Controller port.
        username: The username for unifi controller.
        password: The password for unifi controller.
        ssid_regex: Only APs broadcasting a matching SSID are reported.
        offloader_mac: The MAC of the offloader per site name.
        nodelist: The meshviewer.json URL to look up the offloaders.
        fallback_domain: The domain used if no offloader is found.
        version: The controller version passed to pyunifi.
        ssl_verify: Whether to verify the TLS certificate of the controller.
    """

    controller_url: str
    controller_port: int
    username: str
    password: str
    ssid_regex: str
    offloader_mac: Dict[str, str]
    nodelist: str
    fallback_domain: str
    version: str = "v5"
    ssl_verify: bool = True

    @classmethod
    def from_dict(cls, cfg: Dict[str, str]) -> "ControllerConfig":
        return cls(
            controller_url=cfg["controller_url"],
            controller_port=cfg["controller_port"],
            username=cfg["username"],
            password=cfg["password"],
            ssid_regex=cfg["ssid_regex"],
            offloader_mac=cfg["offloader_mac"],
            nodelist=cfg["nodelist"],
            fallback_domain=cfg.get("fallback_domain", "unifi_respondd_fallback"),
            version=cfg["version"],
            ssl_verify=cfg["ssl_verify"],
        )


def get_client_count_for_ap(ap_mac, clients, cfg):
    """This function returns the number total clients, 2,4Ghz clients and 5Ghz clients connected to an AP."""
    client5_count = 0
    client24_count = 0
    for client in clients:
        if re.search(cfg.ssid_regex, client.get("essid", ""), re.IGNORECASE):
            if client.get("ap_mac", "No mac") == ap_mac:
                if client.get("channel", 0) > 14:
                    client5_count += 1
                else:
                    client24_count += 1
    return client24_count + client5_count, client24_count, client5_count


def get_ap_channel_usage(ssids, cfg):
    """This function returns the channels used for the Freifunk SSIDs"""
    channel5 = None
    rx_bytes5 = None
    tx_bytes5 = None
    channel24 = None
    rx_bytes24 = None
    tx_bytes24 = None
    for ssid in ssids:
        if re.search(cfg.ssid_regex, ssid.get("essid", ""), re.IGNORECASE):
            channel = ssid.get("channel", 0)
            rx_bytes = ssid.get("rx_bytes", 0)
            tx_bytes = ssid.get("tx_bytes", 0)
            if channel > 14:
                channel5 = channel
                rx_bytes5 = rx_bytes
                tx_bytes5 = tx_bytes
            else:
                channel24 = channel
                rx_bytes24 = rx_bytes
                tx_bytes24 = tx_bytes

    return channel5, rx_bytes5, tx_bytes5, channel24, rx_bytes24, tx_bytes24


def frequency_from_channel(channel):
    """This function returns the frequency in MHz of a WiFi channel."""
    if channel >= 36:
        return 5000 + (channel) * 5
    else:
        if channel == 14:
            return 2484
        elif channel < 14:
            return 2407 + (channel) * 5


def get_infos(cfg):
    """This function gathers all the information and returns a list of Accesspoint objects."""
    ffnodes = scrape(cfg.nodelist)
    try:
        c = Controller(
            host=cfg.controller_url,
            username=cfg.username,
            password=cfg.password,
            port=cfg.controller_port,
            version=cfg.version,
            ssl_verify=cfg.ssl_verify,
        )
    except Exception as ex:
        logger.error("Error: %s" % (ex))
        return
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    aps = Accesspoints(accesspoints=[])
    for site in c.get_sites():
        if cfg.version == "UDMP-unifiOS":
            c.site_id = site["name"]
        else:
            try:
                c.switch_site(site["desc"])
            except Exception as ex:
                logger.error("Error: %s" % (ex))
                continue

        try:
            aps_for_site = c.get_aps()
            clients = c.get_clients()
        except Exception as ex:
            logger.error("Error: %s" % (ex))
            continue
        for ap in aps_for_site:
            if (
                ap.get("name", None) is not None
                and ap.get("state", 0) != 0
                and ap.get("type", "na") == "uap"
            ):
                ssids = ap.get("vap_table", None)
                containsSSID = False
                tx = 0
                rx = 0
                if ssids is not None:
                    for ssid in ssids:
                        if re.search(
                            cfg.ssid_regex, ssid.get("essid", ""), re.IGNORECASE
                        ):
                            containsSSID = True
                            tx = tx + ssid.get("tx_bytes", 0)
                            rx = rx + ssid.get("rx_bytes", 0)
                if containsSSID:
                    (
                        client_count,
                        client_count24,
                        client_count5,
                    ) = get_client_count_for_ap(ap.get("mac", None), clients, cfg)

                    (
                        channel5,
                        rx_bytes5,
                        tx_bytes5,
                        channel24,
                        rx_bytes24,
                        tx_bytes24,
                    ) = get_ap_channel_usage(ssids, cfg)

                    lat, lon = 0, 0
                    neighbour_macs = []
                    if ap.get("snmp_location", None):
                        try:
                            lat, lon = get_location_by_address(
                                ap["snmp_location"], geolookup
                            )
                        except Exception:
                            pass
                    offloader_mac, offloader_id, offloader = get_offloader(
                        cfg.offloader_mac, ffnodes, site["desc"]
                    )
                    neighbour_macs.append(offloader_mac)
                    radios = []
                    if channel5:
                        radios.append(
                            Radio(
                                frequency=frequency_from_channel(channel5),
                                rx_bytes=rx_bytes5,
                                tx_bytes=tx_bytes5,
                            )
                        )
                    if channel24:
                        radios.append(
                            Radio(
                                frequency=frequency_from_channel(channel24),
                                rx_bytes=rx_bytes24,
                                tx_bytes=tx_bytes24,
                            )
                        )
                    uplink = ap.get("uplink", None)
                    if uplink is not None and uplink.get("ap_mac", None) is not None:
                        neighbour_macs.append(uplink.get("ap_mac"))
                    lldp_table = ap.get("lldp_table", None)
                    if lldp_table is not None:
                        for lldp_entry in lldp_table:
                            if not lldp_entry.get("is_wired", True):
                                neighbour_macs.append(lldp_entry.get("chassis_id"))
                    aps.accesspoints.append(
                        Accesspoint(
                            name=ap.get("name", None),
                            mac=ap.get("mac", None),
                            client_count=client_count,
                            client_count24=client_count24,
                            client_count5=client_count5,
                            latitude=float(lat),
                            longitude=float(lon),
                            model=ap.get("model", None),
                            firmware=ap.get("version", None),
                            firmware_base="UniFi",
                            uptime=ap.get("uptime", None),
                            contact=ap.get("snmp_contact", None),
                            load_avg=float(
                                ap.get("sys_stats", {}).get("loadavg_1", 0.0)
                            ),
                            mem_used=ap.get("sys_stats", {}).get("mem_used", 0),
                            mem_buffer=ap.get("sys_stats", {}).get("mem_buffer", 0),
                            mem_total=ap.get("sys_stats", {}).get("mem_total", 0),
                            tx_bytes=tx,
                            rx_bytes=rx,
                            gateway=offloader.get("gateway", None),
                            gateway6=offloader.get("gateway6", None),
                            gateway_nexthop=offloader_id,
                            neighbour_macs=neighbour_macs,
                            domain_code=offloader.get("domain", cfg.fallback_domain),
                            radios=radios,
                        )
                    )
    return aps


def main():
    """This function is the main function, it's only executed if we aren't imported."""
    from unified_respondd import config

    print(get_infos(config.Config.from_dict(config.load_config()).controller))


if __name__ == "__main__":
    main()
