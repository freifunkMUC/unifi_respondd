#!/usr/bin/env python3

import re
from typing import List, Optional

from geopy.geocoders import Nominatim
from pyunifi.controller import Controller

from unifi_respondd import logger, net
from unifi_respondd.accesspoint import Accesspoint, WirelessBandInfo
from unifi_respondd.config import ControllerConfig


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


def frequency_from_channel(channel: int) -> Optional[int]:
    """Converts a WiFi channel number to its frequency in MHz."""
    if channel >= 36:
        return 5000 + (channel) * 5
    else:
        if channel == 14:
            return 2484
        elif channel < 14:
            return 2407 + (channel) * 5


def _build_wireless_bands(
    channel5, rx_bytes5, tx_bytes5, channel24, rx_bytes24, tx_bytes24
) -> List[WirelessBandInfo]:
    wireless_bands: List[WirelessBandInfo] = []
    if channel5:
        wireless_bands.append(
            WirelessBandInfo(
                frequency=frequency_from_channel(channel5),
                rx_bytes=rx_bytes5,
                tx_bytes=tx_bytes5,
            )
        )
    if channel24:
        wireless_bands.append(
            WirelessBandInfo(
                frequency=frequency_from_channel(channel24),
                # NOTE: intentionally reusing the 5GHz band's rx/tx values
                # here. This preserves a pre-existing bug from the original
                # respondd_client.py getStatistics() (the channel24 branch
                # used ap.rx_bytes5/ap.tx_bytes5 instead of
                # ap.rx_bytes24/ap.tx_bytes24). Not fixed as part of this
                # merge -- tracked separately.
                rx_bytes=rx_bytes5,
                tx_bytes=tx_bytes5,
            )
        )
    return wireless_bands


def get_accesspoints(
    controller_cfg: ControllerConfig, ffnodes: Optional[dict], fallback_domain: str
) -> List[Accesspoint]:
    """This function gathers all the information for one UniFi controller and
    returns a list of Accesspoint objects. Raises on connection failure --
    the aggregator is responsible for catching and logging per-controller
    failures."""
    cfg = controller_cfg
    c = Controller(
        host=cfg.controller_url,
        username=cfg.username,
        password=cfg.password,
        port=cfg.controller_port,
        version=cfg.version,
        ssl_verify=cfg.ssl_verify,
    )
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    accesspoints: List[Accesspoint] = []
    for site in c.get_sites():
        if cfg.version == "UDMP-unifiOS":
            c = Controller(
                host=cfg.controller_url,
                username=cfg.username,
                password=cfg.password,
                port=cfg.controller_port,
                version=cfg.version,
                site_id=site["name"],
                ssl_verify=cfg.ssl_verify,
            )
        else:
            try:
                c.switch_site(site["desc"])
            except Exception as ex:
                logger.error("Error: %s" % (ex))
                continue

        aps_for_site = c.get_aps()
        clients = c.get_clients()
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
                    if ap.get("snmp_location", None) is not None:
                        try:
                            lat, lon = net.get_location_by_address(
                                ap["snmp_location"], geolookup
                            )
                        except Exception:
                            pass
                    try:
                        neighbour_macs.append(cfg.offloader_mac.get(site["desc"], None))
                        offloader_id = cfg.offloader_mac.get(site["desc"], "").replace(
                            ":", ""
                        )
                        offloader = list(
                            filter(
                                lambda x: x["mac"]
                                == cfg.offloader_mac.get(site["desc"], ""),
                                ffnodes["nodes"],
                            )
                        )[0]
                    except Exception:
                        offloader_id = None
                        offloader = {}
                    uplink = ap.get("uplink", None)
                    if uplink is not None and uplink.get("ap_mac", None) is not None:
                        neighbour_macs.append(uplink.get("ap_mac"))
                    lldp_table = ap.get("lldp_table", None)
                    if lldp_table is not None:
                        for lldp_entry in lldp_table:
                            if not lldp_entry.get("is_wired", True):
                                neighbour_macs.append(lldp_entry.get("chassis_id"))
                    accesspoints.append(
                        Accesspoint(
                            name=ap.get("name", None),
                            mac=ap.get("mac", None),
                            controller_type="unifi",
                            controller_name=cfg.name,
                            firmware_base="UniFi",
                            snmp_location=ap.get("snmp_location", None),
                            latitude=float(lat),
                            longitude=float(lon),
                            contact=ap.get("snmp_contact", None),
                            model=ap.get("model", None),
                            firmware=ap.get("version", None),
                            uptime=ap.get("uptime", None),
                            client_count=client_count,
                            client_count24=client_count24,
                            client_count5=client_count5,
                            wireless_bands=_build_wireless_bands(
                                channel5,
                                rx_bytes5,
                                tx_bytes5,
                                channel24,
                                rx_bytes24,
                                tx_bytes24,
                            ),
                            tx_bytes=tx,
                            rx_bytes=rx,
                            load_avg=float(
                                ap.get("sys_stats", {}).get("loadavg_1", 0.0)
                            ),
                            mem_used=ap.get("sys_stats", {}).get("mem_used", 0),
                            mem_buffer=ap.get("sys_stats", {}).get("mem_buffer", 0),
                            mem_total=ap.get("sys_stats", {}).get("mem_total", 0),
                            gateway=offloader.get("gateway", None),
                            gateway6=offloader.get("gateway6", None),
                            gateway_nexthop=offloader_id,
                            neighbour_macs=neighbour_macs,
                            domain_code=offloader.get("domain", fallback_domain),
                        )
                    )
    return accesspoints
