#!/usr/bin/env python3

import re
from typing import List, Optional

from geopy.geocoders import Nominatim

from unifi_respondd import logger, net
from unifi_respondd.accesspoint import Accesspoint, WirelessBandInfo
from unifi_respondd.config import ControllerConfig
from unifi_respondd.vendors.omada_api import Omada


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


def _build_wireless_bands(frequency24, frequency5) -> List[WirelessBandInfo]:
    wireless_bands: List[WirelessBandInfo] = []
    if frequency24:
        wireless_bands.append(WirelessBandInfo(frequency=frequency24))
    if frequency5:
        wireless_bands.append(WirelessBandInfo(frequency=frequency5))
    return wireless_bands


def get_accesspoints(
    controller_cfg: ControllerConfig, ffnodes: Optional[dict], fallback_domain: str
) -> List[Accesspoint]:
    """This function gathers all the information for one Omada controller and
    returns a list of Accesspoint objects. Raises on connection/login failure
    -- the aggregator is responsible for catching and logging per-controller
    failures."""
    cfg = controller_cfg
    cb = Omada(baseurl=cfg.controller_url, verify=cfg.ssl_verify, verbose=False)
    cb.login(username=cfg.username, password=cfg.password)
    geolookup = Nominatim(user_agent="ffmuc_respondd")
    accesspoints: List[Accesspoint] = []
    for site in cb.getCurrentUser()["privilege"]["sites"]:
        csite = Omada(
            baseurl=cfg.controller_url,
            site=site["name"],
            verify=cfg.ssl_verify,
            verbose=False,
        )
        csite.login(
            username=cfg.username,
            password=cfg.password,
        )
        aps_for_site = csite.getSiteDevices()

        for ap in aps_for_site:
            if (
                ap.get("name", None) is not None
                and (ap.get("status", 0) != 0 and ap.get("status", 0) != 20)
                and ap.get("type") == "ap"
            ):
                ap_mac = ap["mac"]
                moreAPInfos = csite.getSiteAP(mac=ap_mac)
                ssids = moreAPInfos.get("ssidOverrides", None)
                containsSSID = False
                if ssids is not None:
                    for ssid in ssids:
                        if re.search(
                            cfg.ssid_regex, ssid.get("ssid", ""), re.IGNORECASE
                        ):
                            # NOTE: this is a tuple literal (ssid.get(...), False),
                            # which is always truthy, so the ssidEnabled check
                            # below is a no-op -- a pre-existing bug carried
                            # over unchanged from the source project. Not
                            # fixed as part of this merge (only the SNMP
                            # location bug below was approved for a fix);
                            # worth its own follow-up ticket.
                            if (ssid.get("ssidEnabled"), False):  # noqa: F634
                                containsSSID = True

                if containsSSID is False:
                    continue  # Skip AP if Freifunk SSID is missing

                (
                    client_count,
                    client_count24,
                    client_count5,
                ) = get_client_count_for_ap(
                    clients=csite.getSiteClientsAP(apmac=ap_mac), cfg=cfg
                )

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

                neighbour_macs = []
                try:
                    neighbour_macs.append(cfg.offloader_mac.get(site["name"], None))
                    offloader_id = cfg.offloader_mac.get(site["name"], "").replace(
                        ":", ""
                    )
                    offloader = list(
                        filter(
                            lambda x: x["mac"]
                            == cfg.offloader_mac.get(site["name"], ""),
                            ffnodes["nodes"],
                        )
                    )[0]
                except Exception:
                    offloader_id = None
                    offloader = {}

                uplink = ap.get("uplink", None)
                if uplink is not None:
                    neighbour_macs.append(uplink.replace("-", ":"))

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

                snmp = moreAPInfos.get("snmp", None)
                if snmp.get("location", None) is not None:
                    if snmp.get("location", None) != "":
                        try:
                            lat, lon = net.get_location_by_address(
                                snmp["location"], geolookup
                            )
                        except Exception:
                            pass

                # NOTE: this append used to live nested inside the
                # `if snmp.get("location", None) is not None:` block above,
                # which meant any AP with no SNMP location set at all was
                # silently dropped from the output despite passing every
                # other filter. Fixed as part of the multi-controller merge.
                accesspoints.append(
                    Accesspoint(
                        name=ap.get("name", None),
                        mac=ap_mac.replace("-", ":").lower(),
                        controller_type="omada",
                        controller_name=cfg.name,
                        firmware_base="Omada",
                        snmp_location=snmp.get("location", None),
                        latitude=float(lat),
                        longitude=float(lon),
                        contact=snmp.get("contact", None),
                        model=ap.get("showModel", None),
                        firmware=ap.get("version", None),
                        uptime=moreAPInfos.get("uptimeLong", None),
                        client_count=client_count,
                        client_count24=client_count24,
                        client_count5=client_count5,
                        wireless_bands=_build_wireless_bands(frequency24, frequency5),
                        tx_bytes=tx,
                        rx_bytes=rx,
                        load_avg=_extract_loadavg(ap, moreAPInfos),
                        mem_used=mem_used,
                        mem_buffer=mem_buffer,
                        mem_total=mem_total,
                        gateway=offloader.get("gateway", None),
                        gateway6=offloader.get("gateway6", None),
                        gateway_nexthop=offloader_id,
                        neighbour_macs=neighbour_macs,
                        domain_code=offloader.get("domain", fallback_domain),
                    )
                )
    return accesspoints
