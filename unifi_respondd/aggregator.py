#!/usr/bin/env python3
from typing import List

from unifi_respondd import logger, net
from unifi_respondd.accesspoint import Accesspoint
from unifi_respondd.config import Config
from unifi_respondd.vendors import VENDOR_CLIENTS


def get_infos(cfg: Config) -> List[Accesspoint]:
    """Aggregates Accesspoints across every configured controller.

    Never raises and never returns None: a single controller being
    unreachable, misconfigured, or of an unknown type is logged and
    skipped, and the remaining controllers' data is still returned. If
    every controller fails, this returns [] rather than None.
    """
    ffnodes = net.scrape(cfg.nodelist)
    aps: List[Accesspoint] = []

    for controller_cfg in cfg.controllers:
        client_fn = VENDOR_CLIENTS.get(controller_cfg.type)
        if client_fn is None:
            logger.error(
                "Unknown controller type %r for controller %r -- skipping"
                % (controller_cfg.type, controller_cfg.name)
            )
            continue
        try:
            aps.extend(client_fn(controller_cfg, ffnodes, cfg.fallback_domain))
        except Exception as ex:
            logger.error(
                "Controller %r (type=%s, url=%s) failed this cycle: %s"
                % (
                    controller_cfg.name,
                    controller_cfg.type,
                    controller_cfg.controller_url,
                    ex,
                )
            )
            continue

    return aps
