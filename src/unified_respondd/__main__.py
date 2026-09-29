#!/usr/bin/env python3

import argparse
import json
import sys

from unified_respondd import config
from unified_respondd.respondd_client import ResponddClient


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="unified-respondd",
        description="Send the APs of a WiFi controller to respondd queriers.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="query the controller once, print the respondd data as JSON and exit "
        "without sending anything",
    )
    args = parser.parse_args(argv)

    cfg = config.Config.from_dict(config.load_config())
    extResponddClient = ResponddClient(cfg)
    if args.dry_run:
        nodes = extResponddClient.collect()
        if nodes is None:
            print("Could not fetch the APs from the controller", file=sys.stderr)
            return 1
        json.dump(nodes, sys.stdout, indent=2)
        print()
        if extResponddClient.failed_controllers:
            print(
                "Could not fetch the APs from the controllers: "
                + ", ".join(extResponddClient.failed_controllers),
                file=sys.stderr,
            )
            return 1
        return 0
    extResponddClient.start()


if __name__ == "__main__":
    sys.exit(main())
