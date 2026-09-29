#!/usr/bin/env python3

import unified_respondd.config as config
from unified_respondd.respondd_client import ResponddClient


def main():
    cfg = config.Config.from_dict(config.load_config())
    extResponddClient = ResponddClient(cfg)
    extResponddClient.start()


if __name__ == "__main__":
    main()
