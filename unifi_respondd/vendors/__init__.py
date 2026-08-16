#!/usr/bin/env python3
from typing import Callable, Dict, List, Optional

from unifi_respondd.accesspoint import Accesspoint
from unifi_respondd.config import ControllerConfig
from unifi_respondd.vendors import omada, unifi

# Signature every vendor client module's get_accesspoints must implement:
#   get_accesspoints(controller_cfg, ffnodes, fallback_domain) -> List[Accesspoint]
VendorClientFn = Callable[[ControllerConfig, Optional[dict], str], List[Accesspoint]]

VENDOR_CLIENTS: Dict[str, VendorClientFn] = {
    "unifi": unifi.get_accesspoints,
    "omada": omada.get_accesspoints,
}
