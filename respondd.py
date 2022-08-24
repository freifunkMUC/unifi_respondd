#!/usr/bin/env python3

import unifi_respondd.config as config
from unifi_respondd.respondd_client import ResponddClient
import omada_respondd.config as config2
from omada_respondd.respondd_client import ResponddClient as ResponddClient2


def main():
    # cfg = config.Config.from_dict(config.load_config())
    # extResponddClient = ResponddClient(cfg)
    # extResponddClient.start()

    cfg2 = config2.Config.from_dict(config2.load_config())
    extResponddClient2 = ResponddClient2(cfg2)
    extResponddClient2.start()


if __name__ == "__main__":
    main()
