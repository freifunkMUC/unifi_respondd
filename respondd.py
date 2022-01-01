#!/usr/bin/env python3

import socket
import config
import dataclasses
from dataclasses_json import dataclass_json
from typing import List, Dict, Any, Union, Optional
import unifi_respondd
@dataclasses.dataclass
class FirmwareInfo:
    base: str
    release: str

@dataclasses.dataclass
class LocationInfo:
    latitude: float
    longitude: float


@dataclass_json
@dataclasses.dataclass
class NodeInfo:
    firmware: FirmwareInfo
    hostname: str
    node_id: str
    location: LocationInfo

def sendMessage(s, responseData, multicast_address):
    s.sendto(responseData, multicast_address)

def main():
    aps = unifi_respondd.get_infos()
    cfg = config.Config.from_dict(config.load_config())
    for ap in aps.accesspoints:
        print(ap)
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        nodeInfo = NodeInfo(
            firmware=FirmwareInfo(base="", release=""),
            hostname=ap.name,
            node_id=ap.mac.replace(":", ""),
            location=LocationInfo(latitude=ap.latitude, longitude=ap.longitude)
        )
        print(nodeInfo.to_json())
        sendMessage(sock, bytes(nodeInfo.to_json(), 'UTF-8'), (cfg.multicast_address, cfg.multicast_port))
        sock.close()

if __name__ == "__main__":
    main()