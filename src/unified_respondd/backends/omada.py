#!/usr/bin/env python3

import dataclasses
import re
from typing import Dict, Optional

from geopy.geocoders import Nominatim

from unified_respondd import logger
from unified_respondd.backends._omada_api import Omada
from unified_respondd.backends.common import (
    get_location_by_address,
    get_offloader,
    scrape,
)
from unified_respondd.model import Accesspoint, Accesspoints, Radio


@dataclasses.dataclass
class ControllerConfig:
    """The omada specific part of the configuration file.
    Attributes:
        controller_url: The omada controller URL including the port.
        username: The username for omada controller.
        password: The password for omada controller.
        ssid_regex: Only APs broadcasting a matching SSID are reported.
        offloader_mac: The MAC of the offloader per site name.
        nodelist: The meshviewer.json URL to look up the offloaders.
        fallback_domain: The domain used if no offloader is found.
        ssl_verify: Whether to verify the TLS certificate of the controller.
    """

    controller_url: str
    username: str
    # Keep credentials out of logs
    password: str = dataclasses.field(repr=False)
    ssid_regex: str
    offloader_mac: Dict[str, str]
    nodelist: str
    fallback_domain: str
    ssl_verify: bool = True

    @classmethod
    def from_dict(cls, cfg: Dict[str, str]) -> "ControllerConfig":
        return cls(
            controller_url=cfg["controller_url"],
            username=cfg["username"],
            password=cfg["password"],
            ssid_regex=cfg["ssid_regex"],
            offloader_mac=cfg["offloader_mac"],
            nodelist=cfg["nodelist"],
            fallback_domain=cfg.get("fallback_domain", "omada_respondd_fallback"),
            ssl_verify=cfg["ssl_verify"],
        )


def get_client_count_for_ap(clients, cfg):
    """This function returns the number total clients, 2,4Ghz clients and 5Ghz clients connected to an AP with Freifunk SSID."""
    client5_count = 0
    client24_count = 0
    for client in clients:
        if re.search(cfg.ssid_regex, client.get("ssid", ""), re.IGNORECASE):
            if client.get("channel", 0) > 14:
                client5_count += 1
            else:
                client24_count += 1
    return client24_count + client5_count, client24_count, client5_count


def _to_float(value, default=0.0):
    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip().split(" ")[0].replace(",", ".")

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    if value is None:
        return default

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _extract_loadavg(ap, more_ap_infos):
    sys_stats = ap.get("sys_stats", {})
    candidates = [
        sys_stats.get("loadavg_1"),
        sys_stats.get("loadavg1"),
        ap.get("loadavg_1"),
        ap.get("loadavg1"),
        more_ap_infos.get("loadavg_1"),
        more_ap_infos.get("loadavg1"),
    ]

    for candidate in candidates:
        if candidate is not None:
            return _to_float(candidate, 0.0)

    # Some Omada versions only expose CPU utilization; use a scaled value as fallback.
    cpu_util = _to_float(more_ap_infos.get("cpuUtil"), -1.0)
    if 0.0 <= cpu_util <= 100.0:
        return cpu_util / 100.0

    return 0.0


def _extract_memory(ap, more_ap_infos):
    sys_stats = ap.get("sys_stats", {})

    mem_used = _to_int(
        sys_stats.get("mem_used", ap.get("mem_used", more_ap_infos.get("memUsed"))),
        0,
    )
    mem_buffer = _to_int(
        sys_stats.get(
            "mem_buffer", ap.get("mem_buffer", more_ap_infos.get("memBuffer", 0))
        ),
        0,
    )
    mem_total = _to_int(
        sys_stats.get(
            "mem_total", ap.get("mem_total", more_ap_infos.get("memTotal", 0))
        ),
        0,
    )

    if mem_total <= 0:
        mem_util = _to_float(more_ap_infos.get("memUtil"), -1.0)
        if 0.0 <= mem_util <= 100.0:
            mem_total = 100 * 1024
            mem_used = int(mem_total * (mem_util / 100.0))
            mem_buffer = 0

    if mem_total <= 0:
        mem_total = 100 * 1024
    mem_total = max(mem_total, 1024)

    mem_used = min(max(mem_used, 0), mem_total)
    mem_buffer = max(mem_buffer, 0)

    return mem_used, mem_buffer, mem_total


def get_ap_frequency(channelData: str) -> Optional[int]:
    if channelData == "N/A":
        return None
    parts = channelData.split("/")
    # Der zweite Teil enthält die MHz-Zahl
    try:
        return int(parts[1].replace("MHz", "").strip())
    except Exception as ex:
        logger.error(
            "Could not read frequency from channel data (channelData=%s): %s"
            % (channelData, ex)
        )


def get_infos(cfg):
    """This function gathers all the information and returns a list of Accesspoint objects."""
    ffnodes = scrape(cfg.nodelist)
    try:
        cb = Omada(baseurl=cfg.controller_url, verify=cfg.ssl_verify, verbose=False)
        cb.login(username=cfg.username, password=cfg.password)
    except Exception as ex:
        logger.error("Error: %s" % (ex))
        return
    try:
        return get_aps(cb, cfg, ffnodes)
    finally:
        try:
            cb.logout()
        except Exception as ex:
            logger.error("Error: %s" % (ex))


def get_aps(cb, cfg, ffnodes):
    """This function returns the APs of all sites, reusing the logged in session."""
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    aps = Accesspoints(accesspoints=[])
    for site in cb.getCurrentUser()["privilege"]["sites"]:
        try:
            aps_for_site = cb.getSiteDevices(site=site["name"])
        except Exception as ex:
            logger.error("Error: %s" % (ex))
            continue

        for ap in aps_for_site:
            if (
                ap.get("name", None) is not None
                and (ap.get("status", 0) != 0 and ap.get("status", 0) != 20)
                and ap.get("type") == "ap"
            ):
                try:
                    accesspoint = get_accesspoint(
                        cb, site["name"], ap, cfg, ffnodes, geolookup
                    )
                except Exception as ex:
                    logger.error("Error: %s" % (ex))
                    continue
                if accesspoint is not None:
                    aps.accesspoints.append(accesspoint)
    return aps


def get_accesspoint(cb, site_name, ap, cfg, ffnodes, geolookup):
    """This function returns the Accesspoint for an AP of the site.
    Returns None if the AP doesn't broadcast the Freifunk SSID."""
    ap_mac = ap["mac"]
    moreAPInfos = cb.getSiteAP(site=site_name, mac=ap_mac)
    ssids = moreAPInfos.get("ssidOverrides", None)
    containsSSID = False
    if ssids is not None:
        for ssid in ssids:
            if re.search(cfg.ssid_regex, ssid.get("ssid", ""), re.IGNORECASE):
                if ssid.get("ssidEnabled", True):
                    containsSSID = True

    if containsSSID is False:
        return None  # Skip AP if Freifunk SSID is missing

    (
        client_count,
        client_count24,
        client_count5,
    ) = get_client_count_for_ap(
        clients=cb.getSiteClientsAP(site=site_name, apmac=ap_mac),
        cfg=cfg,
    )

    # Traffic from entire AP (TODO: Filter Freifunk for ?SSID?)
    tx = 0
    rx = 0
    radioTraffic2g = moreAPInfos.get("radioTraffic2g", None)
    if radioTraffic2g is not None:
        tx = tx + radioTraffic2g.get("tx", 0)
        rx = rx + radioTraffic2g.get("rx", 0)

    radioTraffic5g = moreAPInfos.get("radioTraffic5g", None)
    if radioTraffic5g is not None:
        tx = tx + radioTraffic5g.get("tx", 0)
        rx = rx + radioTraffic5g.get("rx", 0)

    mem_used, mem_buffer, mem_total = _extract_memory(ap, moreAPInfos)

    frequency24 = None
    wp2g = moreAPInfos.get("wp2g", None)
    if wp2g is not None and wp2g.get("actualChannel", None) is not None:
        frequency24 = get_ap_frequency(wp2g.get("actualChannel"))

    frequency5 = None
    wp5g = moreAPInfos.get("wp5g", None)
    if wp5g is not None and wp5g.get("actualChannel", None) is not None:
        frequency5 = get_ap_frequency(wp5g.get("actualChannel"))

    offloader_mac, offloader_id, offloader = get_offloader(
        cfg.offloader_mac, ffnodes, site_name
    )
    neighbour_macs = [offloader_mac]

    uplink = ap.get("uplink", None)
    if uplink is not None:
        neighbour_macs.append(uplink.replace("-", ":").lower())

    # lldp_table = ap.get("lldp_table", None)
    # if lldp_table is not None:
    # for lldp_entry in lldp_table:
    # if not lldp_entry.get("is_wired", True):
    # neighbour_macs.append(lldp_entry.get("chassis_id"))

    # Location
    lat, lon = 0, 0
    location = moreAPInfos.get("location", None)
    if location is not None:
        if (
            location.get("longitude", None) is not None
            and location.get("latitude", None) is not None
        ):
            lon = location["longitude"]
            lat = location["latitude"]

    snmp = moreAPInfos.get("snmp", None) or {}
    if snmp.get("location", None):
        try:
            lat, lon = get_location_by_address(snmp["location"], geolookup)
        except Exception:
            pass

    return Accesspoint(
        name=ap.get("name", None),
        mac=ap_mac.replace("-", ":").lower(),
        client_count=client_count,
        client_count24=client_count24,
        client_count5=client_count5,
        latitude=float(lat),
        longitude=float(lon),
        model=ap.get("showModel", None),
        firmware=ap.get("version", None),
        firmware_base="Omada",
        uptime=moreAPInfos.get("uptimeLong", None),
        contact=snmp.get("contact", None),
        load_avg=_extract_loadavg(ap, moreAPInfos),
        mem_used=mem_used,
        mem_buffer=mem_buffer,
        mem_total=mem_total,
        tx_bytes=tx,
        rx_bytes=rx,
        gateway=offloader.get("gateway", None),
        gateway6=offloader.get("gateway6", None),
        gateway_nexthop=offloader_id,
        neighbour_macs=neighbour_macs,
        domain_code=offloader.get("domain", cfg.fallback_domain),
        radios=[
            Radio(frequency=frequency)
            for frequency in (frequency24, frequency5)
            if frequency
        ],
    )


def main():
    """This function is the main function, it's only executed if we aren't imported."""
    from unified_respondd import config

    cfg = config.Config.from_dict(config.load_config())
    for controller in cfg.controllers:
        if controller.backend == "omada":
            print(get_infos(controller.config))


if __name__ == "__main__":
    main()
